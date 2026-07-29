"""Leo's tools: the functions the Gemini agent is allowed to call.

These are thin, model-friendly wrappers (clean signatures + clear docstrings) over
our query / memory / prediction code. The Gemini SDK reads each function's docstring
as the tool description and its type hints as the parameter schema, so keep both tidy.
"""

from __future__ import annotations

from . import queries
from .memory import read_memory as _read_memory
from .memory import write_memory as _write_memory
from .predictions import log_prediction as _log_prediction


def read_memory(query: str) -> str:
    """Search your season-long memory (opinions, past discussions, match notes) for a
    topic, and return the most relevant entries. Use this to recall what you believe or
    what you and Rushikesh discussed before."""
    hits = _read_memory(query)
    if not hits:
        return f"Nothing in memory about '{query}'."
    out = [f"Memory hits for '{query}':"]
    for h in hits:
        out.append(f"[{h['source']}] {h['excerpt'][:300]}")
    return "\n\n".join(out)


def write_memory(kind: str, content: str) -> str:
    """Save something to memory so you remember it later. `kind` is 'discussion'
    (something you and Rushikesh talked about, or something he told you he saw in a
    match) or 'opinion' (a take, ideally with the evidence behind it)."""
    kind = (kind or "").lower().strip()
    if kind not in ("discussion", "opinion"):
        kind = "discussion"
    path = _write_memory(kind, content)
    return f"Saved to {path.name} ({kind})."


def log_prediction(
    match: str,
    predicted_result: str,
    confidence: int,
    reasoning: str,
    home_score: int = -1,
    away_score: int = -1,
) -> str:
    """Log a prediction BEFORE a match. Give the match label (e.g. 'Barcelona vs Elche'),
    the predicted result ('HOME_WIN' / 'DRAW' / 'AWAY_WIN'), a confidence from 0-100, your
    reasoning, and optionally a predicted scoreline (home_score, away_score; use -1 if
    you're not calling an exact score)."""
    hs = None if home_score < 0 else home_score
    as_ = None if away_score < 0 else away_score
    _log_prediction(
        match_label=match,
        predicted_result=predicted_result,
        confidence=int(confidence),
        reasoning=reasoning,
        predicted_home_score=hs,
        predicted_away_score=as_,
    )
    return f"Logged prediction for {match}: {predicted_result} ({confidence}%)."


# The full set of tools Leo gets. (score_predictions is Phase 4's review step.)
TOOLS = [
    queries.get_fixtures,
    queries.get_results,
    queries.get_standings,
    queries.get_team_form,
    queries.get_news,
    queries.get_lineups_and_injuries,
    read_memory,
    write_memory,
    log_prediction,
]
