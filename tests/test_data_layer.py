"""Tests for the deterministic parts of the data layer.

We test the PURE functions (parsing, name-normalizing) and the DATABASE round-trip
using a throwaway in-memory DuckDB. None of these touch the network, so they're fast
and always give the same answer.
"""

from __future__ import annotations

import datetime as dt

from companion import db, sources

FETCHED_AT = dt.datetime(2026, 7, 27, 12, 0, 0)


# ---- A tiny fake football-data.org matches payload (shape mirrors the real API) ----
SAMPLE_MATCHES = {
    "matches": [
        {
            "id": 123,
            "season": {"startDate": "2026-08-15"},
            "matchday": 1,
            "utcDate": "2026-08-23T17:00:00Z",
            "status": "SCHEDULED",
            "homeTeam": {"id": 285, "name": "Elche CF"},
            "awayTeam": {"id": 81, "name": "FC Barcelona"},
            "score": {"fullTime": {"home": None, "away": None}},
        }
    ]
}


def test_parse_matches_extracts_expected_fields():
    rows = sources.parse_matches(SAMPLE_MATCHES, "PD", FETCHED_AT)
    assert len(rows) == 1
    row = rows[0]
    assert row["match_id"] == 123
    assert row["competition_code"] == "PD"
    assert row["season"] == 2026
    assert row["home_team_id"] == 285
    assert row["away_team_id"] == 81
    assert row["status"] == "SCHEDULED"
    # An unplayed match has no score yet.
    assert row["home_score"] is None
    # The ISO string with 'Z' should become a real datetime.
    assert row["utc_date"] == dt.datetime(2026, 8, 23, 17, 0, 0)


def test_normalize_team_name_matches_across_sources():
    # The whole point of the teams bridge: different spellings collapse to one key.
    assert sources.normalize_team_name("FC Barcelona") == sources.normalize_team_name("Barcelona")
    assert sources.normalize_team_name("Atlético de Madrid") == sources.normalize_team_name(
        "Atletico Madrid"
    )
    # Different clubs must NOT collide.
    assert sources.normalize_team_name("FC Barcelona") != sources.normalize_team_name(
        "Atletico Madrid"
    )


def test_db_roundtrip_insert_and_read_back():
    con = db.connect(":memory:")
    db.init_schema(con)

    rows = sources.parse_matches(SAMPLE_MATCHES, "PD", FETCHED_AT)
    inserted = db.insert_rows(con, "matches", rows)
    assert inserted == 1

    # Read it back and confirm the stored values survived the round-trip.
    count = con.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    assert count == 1
    home_id, away_id = con.execute(
        "SELECT home_team_id, away_team_id FROM matches WHERE match_id = 123"
    ).fetchone()
    assert (home_id, away_id) == (285, 81)
