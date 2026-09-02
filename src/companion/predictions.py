"""Logging predictions — the front half of the self-evaluation loop.

A prediction is written into DuckDB BEFORE a match (result + scoreline + confidence
+ reasoning). After the match, Phase 4's review fills in the actual result and marks
it correct-or-not. Storing the prediction *before* kickoff is what makes the season
accuracy number honest — we can't quietly rewrite history.
"""

from __future__ import annotations

import re

import duckdb

from .db import DEFAULT_DB_PATH, connect, init_schema, insert_rows, now_utc


def log_prediction(
    match_label: str,
    predicted_result: str,
    confidence: int,
    reasoning: str,
    predicted_home_score: int | None = None,
    predicted_away_score: int | None = None,
    match_id: int | None = None,
    competition_code: str | None = None,
    con: duckdb.DuckDBPyConnection | None = None,
    db_path=DEFAULT_DB_PATH,
) -> dict:
    """Write one prediction row. Returns the row that was stored.

    Pass an open `con` (e.g. an in-memory database) for tests; otherwise it opens
    the real database file and closes it when done.
    """
    owns_connection = con is None
    if con is None:
        con = connect(db_path)
        init_schema(con)

    row = {
        "created_at": now_utc(),
        "match_id": match_id,
        "competition_code": competition_code,
        "match_label": match_label,
        "predicted_result": predicted_result,
        "predicted_home_score": predicted_home_score,
        "predicted_away_score": predicted_away_score,
        "confidence": confidence,
        "reasoning": reasoning,
        "actual_home_score": None,  # filled in later by the review step (Phase 4)
        "actual_away_score": None,
        "correct": None,
    }
    insert_rows(con, "predictions", [row])

    if owns_connection:
        con.close()
    return row


def get_predictions(
    con: duckdb.DuckDBPyConnection | None = None, db_path=DEFAULT_DB_PATH
) -> list[tuple]:
    """Return logged predictions, newest first: (match_label, predicted_result, confidence)."""
    owns_connection = con is None
    if con is None:
        con = connect(db_path)
        init_schema(con)

    rows = con.execute(
        "SELECT match_label, predicted_result, confidence "
        "FROM predictions ORDER BY created_at DESC"
    ).fetchall()

    if owns_connection:
        con.close()
    return rows


# ============================================================================
# The back half of the loop — score predictions against real results.
# ============================================================================

def _actual_result(home_score: int | None, away_score: int | None) -> str | None:
    """Turn a scoreline into HOME_WIN / DRAW / AWAY_WIN (or None if not played)."""
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return "HOME_WIN"
    if home_score < away_score:
        return "AWAY_WIN"
    return "DRAW"


def _result_for(con: duckdb.DuckDBPyConnection, match_label: str):
    """Find the finished result for a 'Team A vs Team B' label. Returns
    (home_score, away_score, actual_result, date) or None if not played/found."""
    from . import queries  # local import avoids any import cycle

    parts = re.split(r"\bvs\b", match_label, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    a_id, _ = queries._resolve_team(con, parts[0].strip())
    b_id, _ = queries._resolve_team(con, parts[1].strip())
    if not (a_id and b_id):
        return None
    ts = queries._latest_ts(con, "matches")
    row = con.execute(
        """SELECT home_score, away_score, home_team_id, utc_date FROM matches
           WHERE fetched_at = ? AND status = 'FINISHED'
             AND ((home_team_id = ? AND away_team_id = ?)
                  OR (home_team_id = ? AND away_team_id = ?))
           ORDER BY utc_date DESC LIMIT 1""",
        (ts, a_id, b_id, b_id, a_id),
    ).fetchone()
    if not row or row[0] is None:
        return None
    home_score, away_score, _, date = row
    return (home_score, away_score, _actual_result(home_score, away_score), date)


def score_predictions(con: duckdb.DuckDBPyConnection | None = None, db_path=DEFAULT_DB_PATH) -> list[dict]:
    """Score every not-yet-scored prediction against the stored results.

    For each prediction with no result yet, find the match's actual result, mark it
    right/wrong, and fill the row in. Predictions whose match hasn't been played are
    left alone. Returns a list describing what got scored this run.
    """
    owns_connection = con is None
    if con is None:
        con = connect(db_path)
        init_schema(con)

    pending = con.execute(
        "SELECT created_at, match_label, predicted_result FROM predictions WHERE correct IS NULL"
    ).fetchall()

    scored: list[dict] = []
    for created_at, label, predicted in pending:
        result = _result_for(con, label)
        if result is None:
            continue  # not played yet (or not found)
        home_score, away_score, actual, date = result
        correct = predicted.upper() == actual
        con.execute(
            """UPDATE predictions SET actual_home_score = ?, actual_away_score = ?, correct = ?
               WHERE created_at = ? AND match_label = ?""",
            (home_score, away_score, correct, created_at, label),
        )
        scored.append(
            {
                "match": label,
                "predicted": predicted,
                "actual": actual,
                "scoreline": f"{home_score}-{away_score}",
                "correct": correct,
                "date": str(date)[:10],
            }
        )

    if owns_connection:
        con.close()
    return scored


def accuracy_stats(con: duckdb.DuckDBPyConnection | None = None, db_path=DEFAULT_DB_PATH) -> dict:
    """Return prediction accuracy so far: overall, by competition, and how many
    predictions are still waiting on a result."""
    owns_connection = con is None
    if con is None:
        con = connect(db_path)
        init_schema(con)

    scored, correct = con.execute(
        "SELECT count(*), coalesce(sum(CASE WHEN correct THEN 1 ELSE 0 END), 0) "
        "FROM predictions WHERE correct IS NOT NULL"
    ).fetchone()
    by_comp = con.execute(
        """SELECT coalesce(competition_code, '?'), count(*),
                  coalesce(sum(CASE WHEN correct THEN 1 ELSE 0 END), 0)
           FROM predictions WHERE correct IS NOT NULL GROUP BY competition_code"""
    ).fetchall()
    pending = con.execute("SELECT count(*) FROM predictions WHERE correct IS NULL").fetchone()[0]

    if owns_connection:
        con.close()
    return {"scored": scored, "correct": correct, "by_competition": by_comp, "pending": pending}
