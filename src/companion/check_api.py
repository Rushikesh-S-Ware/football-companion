"""Phase 0 smoke test: prove our live-football data plumbing works.

Run it with:  python -m companion.check_api

It prints two things using the free football-data.org API:
  1. FC Barcelona's next 5 fixtures
  2. The current La Liga (Primera Division) top 5

Nothing is saved — this is just a handshake with the API to confirm our key and
network path work before we build the real data layer in Phase 1. If you haven't
added your token yet, it prints friendly instructions instead of crashing.
"""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

# Windows terminals default to a legacy encoding (cp1252) that can't print accents
# in Spanish club names ("Atlético", "Athletic"). Switch stdout to UTF-8 to fix it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# football-data.org is a free football API. Its base address and the two IDs we
# need are constants so the "why" is obvious at each call site.
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
BARCELONA_TEAM_ID = 81   # FC Barcelona's team id in football-data.org
LA_LIGA_CODE = "PD"      # "Primera Division" — La Liga's competition code


def _get(path: str, token: str, params: dict | None = None) -> dict:
    """Make one GET request to football-data.org and return the JSON.

    The API authenticates with an "X-Auth-Token" header (not a password in the URL,
    which would be unsafe). timeout= makes us fail fast instead of hanging, and
    raise_for_status() turns any HTTP error into a visible exception.
    """
    response = requests.get(
        f"{FOOTBALL_DATA_BASE}{path}",
        headers={"X-Auth-Token": token},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def barcelona_next_fixtures(token: str, n: int = 5) -> list[dict]:
    """Return Barcelona's next `n` scheduled matches (all competitions)."""
    data = _get(
        f"/teams/{BARCELONA_TEAM_ID}/matches",
        token,
        params={"status": "SCHEDULED", "limit": n},
    )
    return data.get("matches", [])[:n]


def la_liga_top(token: str, n: int = 5) -> list[dict]:
    """Return the top `n` rows of the current La Liga table.

    A competition can return several tables (overall / home / away). We want the
    "TOTAL" table — the normal league standings.
    """
    data = _get(f"/competitions/{LA_LIGA_CODE}/standings", token)
    tables = data.get("standings", [])
    total = next((t for t in tables if t.get("type") == "TOTAL"), None)
    if total is None:
        total = tables[0] if tables else {"table": []}
    return total["table"][:n]


def main() -> None:
    load_dotenv()  # read keys from the .env file into the environment
    token = os.getenv("FOOTBALL_DATA_API_TOKEN")

    if not token:
        print("No FOOTBALL_DATA_API_TOKEN found yet — that's expected for now.\n")
        print("To run this proof:")
        print("  1. Register free at https://www.football-data.org/client/register")
        print("  2. Copy .env.example to .env  (PowerShell:  copy .env.example .env)")
        print("  3. Paste your token into .env, then re-run:")
        print("       python -m companion.check_api")
        return

    print("Contacting football-data.org...\n")

    print("FC Barcelona — next 5 fixtures:")
    fixtures = barcelona_next_fixtures(token)
    if not fixtures:
        print("  (no scheduled fixtures returned — may be the off-season)")
    for match in fixtures:
        date = match["utcDate"][:10]  # keep just the YYYY-MM-DD part
        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]
        competition = match["competition"]["name"]
        print(f"  {date}  {home} vs {away}   ({competition})")

    print("\nLa Liga — current top 5:")
    table = la_liga_top(token)
    if not table:
        print("  (no standings returned — season may not have started yet)")
    for row in table:
        position = row["position"]
        name = row["team"]["name"]
        points = row["points"]
        played = row["playedGames"]
        print(f"  {position}. {name:<24} {points} pts ({played} played)")


if __name__ == "__main__":
    main()
