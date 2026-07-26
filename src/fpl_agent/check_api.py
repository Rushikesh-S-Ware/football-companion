"""Phase 0 smoke test: prove the FPL API is reachable and readable.

Run it with:  python -m fpl_agent.check_api

What it does: fetches the FPL "bootstrap-static" endpoint (one big JSON blob with
every player, team, and gameweek) and prints the 5 most expensive players. If this
works, our whole data pipeline has a foundation. Nothing is saved — this is just a
handshake with the API.
"""

from __future__ import annotations

import sys

import requests

# Windows terminals default to a legacy encoding (cp1252) that can't print the
# "£" symbol, so it shows as garbage. Switching stdout to UTF-8 fixes it. This is
# harmless on macOS/Linux (which are already UTF-8). We guard it because some
# environments give us a stdout object without reconfigure().
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# The public, read-only FPL API. No login or API key needed — this is the same
# data the website itself loads. We only ever READ from it.
BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

# The FPL API rejects requests that don't look like a browser, so we send a
# User-Agent header. This is a normal, polite way to identify our client.
HEADERS = {"User-Agent": "fpl-agent/0.1 (portfolio project)"}

# Prices come as integers in tenths of a million: 130 means £13.0m. We divide by
# 10 for display. Defining it as a constant makes the "why" obvious at the call site.
PRICE_DIVISOR = 10


def fetch_bootstrap() -> dict:
    """Download the bootstrap-static payload and return it as a dict.

    We set a timeout so the script fails fast instead of hanging if the API is
    unreachable, and raise_for_status() turns any HTTP error into an exception we
    can see, rather than silently continuing with bad data.
    """
    response = requests.get(BOOTSTRAP_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def five_most_expensive(bootstrap: dict) -> list[dict]:
    """Return the 5 priciest players from the bootstrap payload.

    In this data, every player is an entry in the "elements" list, and "now_cost"
    is their current price (in tenths of a million). We sort by that, descending.
    """
    players = bootstrap["elements"]
    return sorted(players, key=lambda p: p["now_cost"], reverse=True)[:5]


def main() -> None:
    print("Contacting the FPL API...")
    bootstrap = fetch_bootstrap()

    # A couple of quick sanity numbers so we know the payload looks real.
    n_players = len(bootstrap["elements"])
    n_teams = len(bootstrap["teams"])
    print(f"Success. Loaded {n_players} players across {n_teams} teams.\n")

    print("Top 5 most expensive players:")
    for rank, player in enumerate(five_most_expensive(bootstrap), start=1):
        name = player["web_name"]
        price = player["now_cost"] / PRICE_DIVISOR
        # total_points is season-to-date; handy context next to the price.
        points = player["total_points"]
        print(f"  {rank}. {name:<20} £{price:>4.1f}m   ({points} pts so far)")


if __name__ == "__main__":
    main()
