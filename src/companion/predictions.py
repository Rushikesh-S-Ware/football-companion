"""Logging predictions — the front half of the self-evaluation loop.

A prediction is written into DuckDB BEFORE a match (result + scoreline + confidence
+ reasoning). After the match, Phase 4's review fills in the actual result and marks
it correct-or-not. Storing the prediction *before* kickoff is what makes the season
accuracy number honest — we can't quietly rewrite history.
"""

from __future__ import annotations

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
