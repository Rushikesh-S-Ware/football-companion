"""Data sources: fetch raw data from the APIs/RSS, and parse it into clean rows.

Design idea — separate FETCH (talks to the network, hard to test) from PARSE
(pure functions: dict in, list-of-dicts out, easy to test). Every parse function
takes `fetched_at` so the snapshot timestamp is identical across a single run.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

import feedparser
import requests

# ============================================================================
# Shared little helpers
# ============================================================================

def _parse_iso(value: str | None) -> dt.datetime | None:
    """Turn an ISO timestamp like '2026-08-23T17:00:00Z' into a naive-UTC datetime."""
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _struct_to_dt(struct_time) -> dt.datetime | None:
    """Convert feedparser's time.struct_time (already UTC) into a datetime."""
    if not struct_time:
        return None
    return dt.datetime(*struct_time[:6])


def _strip_html(text: str | None) -> str | None:
    """Remove HTML tags from an RSS summary so we store clean-ish text."""
    if not text:
        return text
    return re.sub(r"<[^>]+>", "", text).strip()


def normalize_team_name(name: str | None) -> str:
    """Squash a club name to a comparable key so two APIs' spellings match.

    'FC Barcelona' and 'Barcelona' must resolve to the same key so we can link
    the two data sources. We strip accents, lowercase, drop common filler tokens
    (fc, cf, de, ...) and punctuation, then glue what's left together.
        'FC Barcelona'        -> 'barcelona'
        'Atlético de Madrid'  -> 'atleticomadrid'
        'Atletico Madrid'     -> 'atleticomadrid'
    Not perfect, but good enough; unmatched teams simply keep a NULL mapping.
    """
    if not name:
        return ""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^a-z0-9 ]", " ", ascii_name.lower())
    filler = {"fc", "cf", "cd", "ud", "rc", "sd", "club", "de", "real", "deportivo"}
    tokens = [t for t in ascii_name.split() if t not in filler]
    return "".join(tokens)


# ============================================================================
# football-data.org — fixtures, results, standings  (source of team ids we use)
# ============================================================================

FD_BASE = "https://api.football-data.org/v4"


def _fd_get(path: str, token: str, params: dict | None = None) -> dict:
    resp = requests.get(
        f"{FD_BASE}{path}", headers={"X-Auth-Token": token}, params=params, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def fetch_competition_matches(token: str, code: str) -> dict:
    """All matches for a competition (e.g. 'PD' = La Liga, 'CL' = Champions League)."""
    return _fd_get(f"/competitions/{code}/matches", token)


def fetch_competition_standings(token: str, code: str) -> dict:
    """The current league table for a competition."""
    return _fd_get(f"/competitions/{code}/standings", token)


def _season_year(season: dict | None) -> int | None:
    if not season:
        return None
    start = season.get("startDate")
    return int(start[:4]) if start else None


def parse_matches(payload: dict, competition_code: str, fetched_at: dt.datetime) -> list[dict]:
    """football-data.org matches payload -> rows for the `matches` table."""
    rows: list[dict] = []
    for match in payload.get("matches", []):
        score_ft = (match.get("score") or {}).get("fullTime") or {}
        rows.append(
            {
                "fetched_at": fetched_at,
                "match_id": match.get("id"),
                "competition_code": competition_code,
                "season": _season_year(match.get("season")),
                "matchday": match.get("matchday"),
                "utc_date": _parse_iso(match.get("utcDate")),
                "status": match.get("status"),
                "home_team_id": (match.get("homeTeam") or {}).get("id"),
                "away_team_id": (match.get("awayTeam") or {}).get("id"),
                "home_score": score_ft.get("home"),
                "away_score": score_ft.get("away"),
            }
        )
    return rows


def parse_standings(payload: dict, competition_code: str, fetched_at: dt.datetime) -> list[dict]:
    """football-data.org standings payload -> rows for the `standings` table.

    A competition returns several tables (TOTAL / HOME / AWAY). We keep TOTAL.
    """
    tables = payload.get("standings", [])
    total = next((t for t in tables if t.get("type") == "TOTAL"), None)
    if total is None:
        return []
    season = _season_year(payload.get("season"))
    rows: list[dict] = []
    for entry in total.get("table", []):
        team = entry.get("team") or {}
        rows.append(
            {
                "fetched_at": fetched_at,
                "competition_code": competition_code,
                "season": season,
                "team_id": team.get("id"),
                "position": entry.get("position"),
                "played_games": entry.get("playedGames"),
                "won": entry.get("won"),
                "draw": entry.get("draw"),
                "lost": entry.get("lost"),
                "points": entry.get("points"),
                "goals_for": entry.get("goalsFor"),
                "goals_against": entry.get("goalsAgainst"),
                "goal_difference": entry.get("goalDifference"),
            }
        )
    return rows


def parse_teams(
    match_payloads: list[dict],
    standings_payloads: list[dict],
    api_football_index: dict[str, int],
    fetched_at: dt.datetime,
) -> list[dict]:
    """Collect every unique club seen in the payloads into `teams` rows.

    `api_football_index` maps a normalized name -> API-Football team id, so we can
    fill in `api_football_id` (the bridge between our two data sources). Teams we
    can't match just get NULL there.
    """
    teams: dict[int, dict] = {}

    def add(team: dict | None) -> None:
        if team and team.get("id"):
            teams[team["id"]] = {
                "team_id": team["id"],
                "name": team.get("name"),
                "short_name": team.get("shortName") or team.get("tla"),
            }

    for payload in match_payloads:
        for match in payload.get("matches", []):
            add(match.get("homeTeam"))
            add(match.get("awayTeam"))
    for payload in standings_payloads:
        for table in payload.get("standings", []):
            for entry in table.get("table", []):
                add(entry.get("team"))

    rows: list[dict] = []
    for team in teams.values():
        rows.append(
            {
                **team,
                "api_football_id": api_football_index.get(normalize_team_name(team["name"])),
                "fetched_at": fetched_at,
            }
        )
    return rows


# ============================================================================
# API-Football — team-id bridge + injuries  (lineups come once matches are near)
# ============================================================================

AF_BASE = "https://v3.football.api-sports.io"


def _af_get(path: str, key: str, params: dict | None = None) -> dict:
    resp = requests.get(
        f"{AF_BASE}{path}", headers={"x-apisports-key": key}, params=params, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def fetch_league_teams(key: str, league: int = 140, season: int = 2026) -> dict:
    """All teams in a league/season (140 = La Liga) — used to bridge team ids."""
    return _af_get("/teams", key, params={"league": league, "season": season})


def fetch_injuries(key: str, league: int = 140, season: int = 2026) -> dict:
    """Current injuries/suspensions for a league/season (may be empty pre-season)."""
    return _af_get("/injuries", key, params={"league": league, "season": season})


def parse_af_team_index(payload: dict) -> dict[str, int]:
    """API-Football /teams payload -> {normalized name: api_football team id}."""
    index: dict[str, int] = {}
    for item in payload.get("response", []):
        team = item.get("team") or {}
        if team.get("id") and team.get("name"):
            index[normalize_team_name(team["name"])] = team["id"]
    return index


def parse_injuries(
    payload: dict, af_id_to_team_id: dict[int, int], fetched_at: dt.datetime
) -> list[dict]:
    """API-Football /injuries payload -> rows for the `injuries` table.

    We translate API-Football's team id to OUR canonical team_id via the bridge
    map. Unmapped teams get a NULL team_id rather than being dropped.
    """
    rows: list[dict] = []
    for item in payload.get("response", []):
        team = item.get("team") or {}
        player = item.get("player") or {}
        fixture = item.get("fixture") or {}
        rows.append(
            {
                "fetched_at": fetched_at,
                "team_id": af_id_to_team_id.get(team.get("id")),
                "player_name": player.get("name"),
                "type": player.get("type"),
                "reason": player.get("reason"),
                "fixture_date": _parse_iso(fixture.get("date")),
            }
        )
    return rows


# ============================================================================
# RSS news — no key needed
# ============================================================================

# A few reliable football feeds. We store the source name alongside each item.
NEWS_FEEDS = {
    "Guardian Football": "https://www.theguardian.com/football/rss",
    "BBC Football": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "ESPN Soccer": "https://www.espn.com/espn/rss/soccer/news",
}


def fetch_and_parse_news(fetched_at: dt.datetime, feeds: dict[str, str] | None = None) -> list[dict]:
    """Read each RSS feed and return rows for the `news` table.

    feedparser both downloads and parses the feed, so there's no separate fetch
    step here. A broken feed is skipped rather than crashing the whole ingest.
    """
    feeds = feeds or NEWS_FEEDS
    rows: list[dict] = []
    for source, url in feeds.items():
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            rows.append(
                {
                    "fetched_at": fetched_at,
                    "source": source,
                    "title": entry.get("title"),
                    "url": entry.get("link"),
                    "published_at": _struct_to_dt(entry.get("published_parsed")),
                    "summary": _strip_html(entry.get("summary")),
                }
            )
    return rows
