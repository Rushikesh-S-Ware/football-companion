"""Tests for the prediction-scoring loop (Phase 4), using an in-memory DuckDB."""

from __future__ import annotations

import datetime as dt

from companion import db, predictions


def _seed(con):
    """Two teams and one finished match: Elche 0-2 Barcelona."""
    ts = dt.datetime(2026, 4, 1, 12, 0, 0)
    db.insert_rows(
        con,
        "teams",
        [
            {"team_id": 1, "name": "FC Barcelona", "short_name": "Barça", "api_football_id": None, "fetched_at": ts},
            {"team_id": 2, "name": "Elche CF", "short_name": "Elche", "api_football_id": None, "fetched_at": ts},
        ],
    )
    db.insert_rows(
        con,
        "matches",
        [
            {
                "fetched_at": ts, "match_id": 999, "competition_code": "PD", "season": 2025,
                "matchday": 30, "utc_date": dt.datetime(2026, 3, 30, 19, 0, 0), "status": "FINISHED",
                "home_team_id": 2, "away_team_id": 1, "home_score": 0, "away_score": 2,
            }
        ],
    )


def test_score_predictions_marks_correct():
    con = db.connect(":memory:")
    db.init_schema(con)
    _seed(con)

    # Leo predicted the away team (Barça) to win — and they did (0-2).
    predictions.log_prediction(
        match_label="Elche CF vs FC Barcelona",
        predicted_result="AWAY_WIN",
        confidence=80,
        reasoning="Quality gap.",
        competition_code="PD",
        con=con,
    )

    scored = predictions.score_predictions(con=con)
    assert len(scored) == 1
    assert scored[0]["actual"] == "AWAY_WIN"
    assert scored[0]["correct"] is True

    stats = predictions.accuracy_stats(con=con)
    assert stats["scored"] == 1 and stats["correct"] == 1


def test_score_predictions_marks_wrong():
    con = db.connect(":memory:")
    db.init_schema(con)
    _seed(con)

    # Leo predicted a home win — wrong (it was 0-2 to the away side).
    predictions.log_prediction(
        match_label="Elche CF vs FC Barcelona",
        predicted_result="HOME_WIN",
        confidence=40,
        reasoning="Home advantage.",
        competition_code="PD",
        con=con,
    )
    scored = predictions.score_predictions(con=con)
    assert scored[0]["correct"] is False
    assert predictions.accuracy_stats(con=con)["correct"] == 0
