"""The `ingest` command: pull fresh data from every source into DuckDB.

Run it with:  python -m companion.ingest

It fetches La Liga + Champions League fixtures/results/standings (football-data.org),
football news (RSS), and injuries + a team-id bridge (API-Football), then appends a
timestamped snapshot to the database. Each source is wrapped so that one failing
source (e.g. a rate limit) doesn't sink the whole run — we print a per-source summary.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from . import sources
from .db import connect, init_schema, insert_rows, now_utc, replace_rows, DEFAULT_DB_PATH

# Windows terminals default to cp1252, which can't print accented club names.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# The competitions we follow: La Liga and the Champions League.
COMPETITIONS = ["PD", "CL"]


def run_ingest(db_path=DEFAULT_DB_PATH) -> dict[str, object]:
    """Do one full ingest. Returns a {step: count-or-error} summary dict."""
    load_dotenv()
    fd_token = os.getenv("FOOTBALL_DATA_API_TOKEN")
    af_key = os.getenv("API_FOOTBALL_KEY")
    fetched_at = now_utc()

    # API-Football's FREE plan cannot access the current season (only ~2022–2024),
    # so it can't give us live lineups/injuries. We leave it OFF by default to save
    # the 100/day quota, but keep the code ready. Set INGEST_API_FOOTBALL=1 in .env
    # to switch it on (e.g. if you upgrade the plan). See LEARNING_LOG.md.
    use_af = bool(af_key) and os.getenv("INGEST_API_FOOTBALL", "0") == "1"

    con = connect(db_path)
    init_schema(con)
    summary: dict[str, object] = {}

    # --- football-data.org: matches + standings (also feeds the teams table) ---
    match_payloads: list[dict] = []
    standings_payloads: list[dict] = []
    for code in COMPETITIONS:
        try:
            payload = sources.fetch_competition_matches(fd_token, code)
            match_payloads.append(payload)
            rows = sources.parse_matches(payload, code, fetched_at)
            summary[f"matches[{code}]"] = insert_rows(con, "matches", rows)
        except Exception as exc:  # noqa: BLE001 — keep going if one source fails
            summary[f"matches[{code}]"] = f"ERROR: {exc}"
        try:
            payload = sources.fetch_competition_standings(fd_token, code)
            standings_payloads.append(payload)
            rows = sources.parse_standings(payload, code, fetched_at)
            summary[f"standings[{code}]"] = insert_rows(con, "standings", rows)
        except Exception as exc:  # noqa: BLE001
            summary[f"standings[{code}]"] = f"ERROR: {exc}"

    # --- API-Football: bridge team ids (so injuries/lineups can join later) ---
    af_index: dict[str, int] = {}
    if use_af:
        try:
            af_index = sources.parse_af_team_index(sources.fetch_league_teams(af_key))
        except Exception as exc:  # noqa: BLE001
            summary["api_football_teams"] = f"ERROR: {exc}"
    else:
        summary["api_football"] = "skipped (free plan: no current-season access)"

    # --- teams (reference table, refreshed in place) ---
    try:
        team_rows = sources.parse_teams(match_payloads, standings_payloads, af_index, fetched_at)
        summary["teams"] = replace_rows(con, "teams", team_rows)
        # Only report bridge coverage when API-Football is actually in use.
        if use_af:
            summary["teams_bridged"] = sum(
                1 for t in team_rows if t["api_football_id"] is not None
            )
    except Exception as exc:  # noqa: BLE001
        summary["teams"] = f"ERROR: {exc}"
        team_rows = []

    # --- API-Football: injuries (translated to our team ids via the bridge) ---
    if use_af:
        try:
            af_to_team = {
                t["api_football_id"]: t["team_id"]
                for t in team_rows
                if t.get("api_football_id") is not None
            }
            payload = sources.fetch_injuries(af_key)
            rows = sources.parse_injuries(payload, af_to_team, fetched_at)
            summary["injuries"] = insert_rows(con, "injuries", rows)
        except Exception as exc:  # noqa: BLE001
            summary["injuries"] = f"ERROR: {exc}"

    # --- RSS news ---
    try:
        rows = sources.fetch_and_parse_news(fetched_at)
        summary["news"] = insert_rows(con, "news", rows)
    except Exception as exc:  # noqa: BLE001
        summary["news"] = f"ERROR: {exc}"

    con.close()
    return summary


def main() -> None:
    print("Ingesting fresh football data into DuckDB...\n")
    summary = run_ingest()
    width = max(len(k) for k in summary) if summary else 0
    for step, result in summary.items():
        print(f"  {step:<{width}}  {result}")
    print(f"\nDone. Database: {DEFAULT_DB_PATH}")


if __name__ == "__main__":
    main()
