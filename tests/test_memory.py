"""Tests for the memory tools and the predictions table (deterministic parts)."""

from __future__ import annotations

from companion import db, memory, predictions


def test_write_then_read_memory(tmp_path):
    # Write a discussion into a throwaway memory folder, then find it by keyword.
    memory.write_memory("discussion", "Pedri dropped deep to beat the press.", memory_dir=tmp_path)

    results = memory.read_memory("Pedri", memory_dir=tmp_path)
    assert len(results) == 1
    assert results[0]["source"].endswith("discussions.md")
    assert "Pedri" in results[0]["excerpt"]


def test_read_memory_keyword_filter(tmp_path):
    # Two files; a specific query should return only the matching one.
    memory.write_memory("discussion", "Talked about Lewandowski's finishing.", memory_dir=tmp_path)
    memory.write_memory("opinion", "Barça press well from the front.", memory_dir=tmp_path)

    hits = memory.read_memory("Lewandowski", memory_dir=tmp_path)
    assert len(hits) == 1
    assert hits[0]["source"].endswith("discussions.md")

    # A word in neither file returns nothing.
    assert memory.read_memory("Mbappe", memory_dir=tmp_path) == []


def test_write_match_note_creates_file(tmp_path):
    path = memory.write_memory(
        "match_note", "# Test note\nResult: 2-1", slug="2026-08-23_barcelona-vs-elche", memory_dir=tmp_path
    )
    assert path.exists()
    assert path.name == "2026-08-23_barcelona-vs-elche.md"
    assert "Result: 2-1" in path.read_text(encoding="utf-8")


def test_log_prediction_roundtrip():
    con = db.connect(":memory:")
    db.init_schema(con)

    predictions.log_prediction(
        match_label="Barcelona vs Elche",
        predicted_result="HOME_WIN",
        confidence=70,
        reasoning="Home form + opponent just promoted.",
        predicted_home_score=2,
        predicted_away_score=0,
        con=con,
    )

    rows = predictions.get_predictions(con=con)
    assert len(rows) == 1
    assert rows[0] == ("Barcelona vs Elche", "HOME_WIN", 70)
