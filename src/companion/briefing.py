"""`python -m companion.briefing --next-barca`  (or `--match "Barcelona vs Elche"`)

Writes a pre-match briefing to briefings/<date>_<match>.md and logs Leo's prediction.

To stay light on the free-tier rate limit, we gather the data ourselves (from the
DuckDB snapshot) and ask Leo for the whole briefing in a SINGLE Gemini call, rather
than letting him make many tool round-trips.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from google.genai import types

from . import agent, queries
from .db import connect
from .memory import read_memory
from .predictions import log_prediction

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BRIEFINGS_DIR = agent.SYSTEM_PROMPT_PATH.resolve().parents[2] / "briefings"


def _next_barca_match(con):
    """Return Barça's next scheduled match: (date, home, away, comp, home_id, away_id)."""
    ts = queries._latest_ts(con, "matches")
    bid, _ = queries._resolve_team(con, "FC Barcelona")
    if ts is None or not bid:
        return None
    return con.execute(
        """SELECT m.utc_date, h.name, a.name, m.competition_code, m.home_team_id, m.away_team_id
           FROM matches m JOIN teams h ON m.home_team_id = h.team_id
           JOIN teams a ON m.away_team_id = a.team_id
           WHERE m.fetched_at = ? AND m.status = 'SCHEDULED'
             AND (m.home_team_id = ? OR m.away_team_id = ?)
           ORDER BY m.utc_date LIMIT 1""",
        (ts, bid, bid),
    ).fetchone()


def _gather(home: str, away: str, competition: str) -> str:
    """Pull all the facts Leo should use, from the cached DB + memory."""
    parts = [
        f"STANDINGS:\n{queries.get_standings(competition)}",
        f"\n{home} FORM:\n{queries.get_team_form(home)}",
        f"\n{away} FORM:\n{queries.get_team_form(away)}",
        f"\nRECENT NEWS HEADLINES:\n{queries.get_news('')}",
        f"\nTEAM NEWS / INJURIES:\n{queries.get_lineups_and_injuries(home)}",
    ]
    mem = read_memory("Barça press La Masia possession")
    if mem:
        excerpts = "\n".join(f"- {m['excerpt'][:200]}" for m in mem[:3])
        parts.append(f"\nYOUR RELEVANT OPINIONS (from memory):\n{excerpts}")
    return "\n".join(parts)


PROMPT = """You're writing a PRE-MATCH BRIEFING for: {match} on {date} ({competition}).

Here is the data I pulled for you. Use ONLY this — do not invent stats or results.
If something is missing (it's pre-season, so form/head-to-head may be empty), say so
honestly rather than making things up.

{data}

Write the briefing in your own voice (Leo), with these sections:
## Form
## Head-to-head
## Team news & likely angle
## The tactical read

Then finish with EXACTLY this block, filled in (keep the labels):

## Prediction
Result: HOME_WIN or DRAW or AWAY_WIN
Scoreline: X-Y
Confidence: NN%
Reasoning: one or two sentences
"""


def _parse_prediction(text: str) -> dict | None:
    """Pull the structured prediction out of Leo's briefing text."""
    result = re.search(r"Result:\s*(HOME_WIN|DRAW|AWAY_WIN)", text, re.I)
    score = re.search(r"Scoreline:\s*(\d+)\s*-\s*(\d+)", text)
    conf = re.search(r"Confidence:\s*(\d+)", text)
    reason = re.search(r"Reasoning:\s*(.+)", text)
    if not (result and conf):
        return None
    return {
        "result": result.group(1).upper(),
        "home_score": int(score.group(1)) if score else None,
        "away_score": int(score.group(2)) if score else None,
        "confidence": int(conf.group(1)),
        "reasoning": reason.group(1).strip() if reason else "",
    }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def run_briefing(match_arg: str | None = None) -> None:
    con = connect()
    if match_arg:
        # Best-effort: find a scheduled match between the two named teams.
        try:
            a, b = [s.strip() for s in re.split(r"\bvs\b|-", match_arg, maxsplit=1)]
        except ValueError:
            print('Use --match "Team A vs Team B".')
            return
        aid, aname = queries._resolve_team(con, a)
        bid, bname = queries._resolve_team(con, b)
        ts = queries._latest_ts(con, "matches")
        row = con.execute(
            """SELECT m.utc_date, h.name, a.name, m.competition_code, m.home_team_id, m.away_team_id
               FROM matches m JOIN teams h ON m.home_team_id=h.team_id JOIN teams a ON m.away_team_id=a.team_id
               WHERE m.fetched_at=? AND ((m.home_team_id=? AND m.away_team_id=?) OR (m.home_team_id=? AND m.away_team_id=?))
               ORDER BY m.utc_date LIMIT 1""",
            (ts, aid, bid, bid, aid),
        ).fetchone()
    else:
        row = _next_barca_match(con)
    con.close()

    if not row:
        print("Couldn't find that match in the stored fixtures. (Run `ingest` first?)")
        return

    date_val, home, away, comp, _, _ = row
    date_str = str(date_val)[:10]
    match = f"{home} vs {away}"
    comp_name = "La Liga" if comp == "PD" else ("Champions League" if comp == "CL" else comp)

    print(f"Gathering data and writing Leo's briefing for {match} ({date_str})...\n")
    data = _gather(home, away, comp_name)
    prompt = PROMPT.format(match=match, date=date_str, competition=comp_name, data=data)

    client = agent.make_client()
    try:
        resp = client.models.generate_content(
            model=agent.MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=agent.load_system_prompt()),
        )
        briefing_text = resp.text
    except Exception as exc:  # noqa: BLE001
        print(f"[Gemini error — probably the free-tier rate limit: {exc}]")
        return

    # Save the briefing file.
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEFINGS_DIR / f"{date_str}_{_slug(match)}.md"
    header = f"# Pre-match briefing — {match}\n_{comp_name} · {date_str} · written by Leo_\n\n"
    path.write_text(header + briefing_text, encoding="utf-8")
    print(briefing_text)
    print(f"\n📝 Saved briefing to {path}")

    # Log the prediction it made.
    pred = _parse_prediction(briefing_text)
    if pred:
        log_prediction(
            match_label=match,
            predicted_result=pred["result"],
            confidence=pred["confidence"],
            reasoning=pred["reasoning"],
            predicted_home_score=pred["home_score"],
            predicted_away_score=pred["away_score"],
            match_id=None,
            competition_code=comp,
        )
        score = (
            f" {pred['home_score']}-{pred['away_score']}"
            if pred["home_score"] is not None
            else ""
        )
        print(f"✅ Logged prediction: {pred['result']}{score} ({pred['confidence']}%)")
    else:
        print("⚠️ Couldn't parse a prediction from the briefing — not logged.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a pre-match briefing + log a prediction.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--next-barca", action="store_true", help="Barça's next fixture (default)")
    group.add_argument("--match", type=str, help='e.g. "Barcelona vs Elche"')
    args = parser.parse_args()
    run_briefing(match_arg=args.match)


if __name__ == "__main__":
    main()
