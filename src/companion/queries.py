"""Read-from-DuckDB functions that power Leo's data tools.

These read the LATEST snapshot we've ingested (never the live API), format the
answer as readable text, and hand it to the agent. Team and competition names are
resolved loosely, so "Barcelona", "Barça", and "FC Barcelona" all match.
"""

from __future__ import annotations

from .db import connect
from .sources import normalize_team_name


def _resolve_competition(text: str) -> str | None:
    """Map free text like 'la liga' / 'UCL' to a competition code ('PD' / 'CL')."""
    t = (text or "").lower()
    if any(k in t for k in ["la liga", "laliga", "primera", "spain", "spanish"]) or t == "pd":
        return "PD"
    if any(k in t for k in ["champions", "ucl", "europe"]) or t == "cl":
        return "CL"
    return None


def _resolve_team(con, text: str) -> tuple[int | None, str | None]:
    """Best-effort match of a team name to (team_id, canonical_name)."""
    if not text:
        return (None, None)
    target = normalize_team_name(text)
    rows = con.execute("SELECT team_id, name FROM teams").fetchall()
    for tid, name in rows:  # exact normalized match first
        if normalize_team_name(name) == target:
            return (tid, name)
    for tid, name in rows:  # then a loose contains match
        n = normalize_team_name(name)
        if target and (target in n or n in target):
            return (tid, name)
    return (None, None)


def _latest_ts(con, table: str, where: str = "", params: tuple = ()):
    """The most recent fetched_at for a table (optionally filtered)."""
    query = f"SELECT max(fetched_at) FROM {table}"
    if where:
        query += f" WHERE {where}"
    row = con.execute(query, params).fetchone()
    return row[0] if row else None


def get_standings(competition: str = "La Liga") -> str:
    """Return the current league table for a competition ('La Liga' or 'Champions League')."""
    code = _resolve_competition(competition) or "PD"
    con = connect()
    ts = _latest_ts(con, "standings", "competition_code = ?", (code,))
    if ts is None:
        con.close()
        return f"No standings stored yet for {competition}. (Run `ingest` first.)"
    rows = con.execute(
        """SELECT s.position, t.name, s.played_games, s.won, s.draw, s.lost, s.points
           FROM standings s JOIN teams t ON s.team_id = t.team_id
           WHERE s.competition_code = ? AND s.fetched_at = ?
           ORDER BY s.position""",
        (code, ts),
    ).fetchall()
    con.close()
    lines = [f"{code} table (as of {str(ts)[:10]}):"]
    for pos, name, pl, w, d, l, pts in rows:
        lines.append(f"{pos}. {name} — {pts} pts ({pl} pl, {w}W {d}D {l}L)")
    return "\n".join(lines)


def get_fixtures(team_or_competition: str = "Barcelona", next_n: int = 5) -> str:
    """Return the next upcoming fixtures for a team or a competition."""
    con = connect()
    ts = _latest_ts(con, "matches")
    if ts is None:
        con.close()
        return "No fixtures stored yet. (Run `ingest` first.)"
    tid, tname = _resolve_team(con, team_or_competition)
    code = _resolve_competition(team_or_competition)
    sql = (
        "SELECT m.utc_date, h.name, a.name, m.competition_code FROM matches m "
        "JOIN teams h ON m.home_team_id = h.team_id JOIN teams a ON m.away_team_id = a.team_id "
        "WHERE m.fetched_at = ? AND m.status = 'SCHEDULED'"
    )
    params: list = [ts]
    if tid:
        sql += " AND (m.home_team_id = ? OR m.away_team_id = ?)"
        params += [tid, tid]
    elif code:
        sql += " AND m.competition_code = ?"
        params.append(code)
    sql += " ORDER BY m.utc_date LIMIT ?"
    params.append(next_n)
    rows = con.execute(sql, params).fetchall()
    con.close()
    who = tname or team_or_competition
    if not rows:
        return f"No upcoming fixtures found for {who}."
    lines = [f"Next {len(rows)} fixtures for {who}:"]
    for d, h, a, c in rows:
        lines.append(f"{str(d)[:10]}: {h} vs {a} ({c})")
    return "\n".join(lines)


def get_results(team_or_competition: str = "Barcelona", last_n: int = 5) -> str:
    """Return recent finished results for a team or competition."""
    con = connect()
    ts = _latest_ts(con, "matches")
    if ts is None:
        con.close()
        return "No results stored yet. (Run `ingest` first.)"
    tid, tname = _resolve_team(con, team_or_competition)
    code = _resolve_competition(team_or_competition)
    sql = (
        "SELECT m.utc_date, h.name, a.name, m.home_score, m.away_score, m.competition_code "
        "FROM matches m JOIN teams h ON m.home_team_id = h.team_id "
        "JOIN teams a ON m.away_team_id = a.team_id "
        "WHERE m.fetched_at = ? AND m.status = 'FINISHED'"
    )
    params: list = [ts]
    if tid:
        sql += " AND (m.home_team_id = ? OR m.away_team_id = ?)"
        params += [tid, tid]
    elif code:
        sql += " AND m.competition_code = ?"
        params.append(code)
    sql += " ORDER BY m.utc_date DESC LIMIT ?"
    params.append(last_n)
    rows = con.execute(sql, params).fetchall()
    con.close()
    who = tname or team_or_competition
    if not rows:
        return f"No finished results found for {who} (the season may not have started yet)."
    lines = [f"Last {len(rows)} results for {who}:"]
    for d, h, a, hs, as_, c in rows:
        lines.append(f"{str(d)[:10]}: {h} {hs}-{as_} {a} ({c})")
    return "\n".join(lines)


def get_team_form(team: str = "Barcelona") -> str:
    """Return a team's recent form — its last few finished matches as W/D/L."""
    con = connect()
    ts = _latest_ts(con, "matches")
    tid, tname = _resolve_team(con, team)
    if ts is None or not tid:
        con.close()
        return f"No form data for {team} yet."
    rows = con.execute(
        """SELECT m.home_team_id, m.home_score, m.away_score, h.name, a.name, m.utc_date
           FROM matches m JOIN teams h ON m.home_team_id = h.team_id
           JOIN teams a ON m.away_team_id = a.team_id
           WHERE m.fetched_at = ? AND m.status = 'FINISHED'
             AND (m.home_team_id = ? OR m.away_team_id = ?)
           ORDER BY m.utc_date DESC LIMIT 5""",
        (ts, tid, tid),
    ).fetchall()
    con.close()
    if not rows:
        return f"No finished matches for {tname} yet (the season may not have started)."
    form, lines = [], [f"{tname} recent form:"]
    for home_id, hs, as_, hname, aname, d in rows:
        if hs is None:
            continue
        is_home = home_id == tid
        gf, ga = (hs, as_) if is_home else (as_, hs)
        result = "W" if gf > ga else ("D" if gf == ga else "L")
        form.append(result)
        opp = aname if is_home else hname
        lines.append(f"{str(d)[:10]}: {result} {gf}-{ga} vs {opp}")
    lines.insert(1, "Form (recent → older): " + " ".join(form))
    return "\n".join(lines)


def get_news(topic: str = "", since: str = "") -> str:
    """Return recent football news headlines, optionally filtered by a topic keyword."""
    con = connect()
    ts = _latest_ts(con, "news")
    if ts is None:
        con.close()
        return "No news stored yet. (Run `ingest` first.)"
    rows = con.execute(
        "SELECT title, source FROM news WHERE fetched_at = ? ORDER BY published_at DESC",
        (ts,),
    ).fetchall()
    con.close()
    if topic:
        k = topic.lower()
        rows = [r for r in rows if r[0] and k in r[0].lower()]
    rows = rows[:8]
    if not rows:
        return f"No recent headlines{f' about {topic}' if topic else ''}."
    label = f" about {topic}" if topic else ""
    lines = [f"Recent headlines{label}:"]
    for title, src in rows:
        lines.append(f"[{src}] {title}")
    return "\n".join(lines)


def get_lineups_and_injuries(team_or_match: str = "Barcelona") -> str:
    """Return lineups/injuries if available (often empty in v1: the free API-Football tier
    doesn't cover the current season)."""
    con = connect()
    injuries = con.execute("SELECT count(*) FROM injuries").fetchone()[0]
    lineups = con.execute("SELECT count(*) FROM lineups").fetchone()[0]
    con.close()
    if injuries == 0 and lineups == 0:
        return (
            "I don't have structured lineup or injury data — the free API-Football tier "
            "doesn't cover the current season. Best I can do is check the news for team-news, "
            "or you can tell me what you've read and I'll remember it."
        )
    return f"Stored injury rows: {injuries}, lineup rows: {lineups}."
