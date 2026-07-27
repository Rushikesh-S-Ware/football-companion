-- ============================================================================
-- Football Companion — DuckDB schema  (Design B: normalized on teams)
--
-- DESIGN PHILOSOPHY — snapshots, append-only:
--   Every ingest run INSERTs new rows stamped with `fetched_at`. We NEVER UPDATE
--   or DELETE. To read the "latest" state, we query the most recent fetched_at.
--   This is what lets the companion remember what the table looked like months ago.
--
--   The ONE exception is `teams` — a small reference ("dimension") table of clubs
--   that we refresh in place, because team names/ids barely change.
--
-- This file is Rushikesh's artifact. Edit column names/types freely, then we build
-- ingestion against it.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- teams — the master club list. Solves the cross-API naming problem: the same
-- club has DIFFERENT names and ids in our two sources, so we keep ONE canonical
-- row per club and store both source ids for reliable joins later.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    team_id          INTEGER PRIMARY KEY,  -- our canonical id (= football-data.org id)
    name             VARCHAR NOT NULL,     -- e.g. 'FC Barcelona'
    short_name       VARCHAR,              -- e.g. 'Barça' or TLA 'BAR'
    api_football_id  INTEGER,              -- same club's id in API-Football (for joins)
    fetched_at       TIMESTAMP NOT NULL    -- when we last refreshed this row
);

-- ---------------------------------------------------------------------------
-- matches — fixtures & results as append-only snapshots. A match reappears each
-- ingest as its status/score changes (SCHEDULED -> IN_PLAY -> FINISHED).
-- Source: football-data.org.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matches (
    fetched_at        TIMESTAMP NOT NULL,  -- snapshot time
    match_id          INTEGER NOT NULL,    -- football-data.org match id
    competition_code  VARCHAR NOT NULL,    -- 'PD' = La Liga, 'CL' = Champions League
    season            INTEGER,             -- season's starting year, e.g. 2026
    matchday          INTEGER,             -- round number
    utc_date          TIMESTAMP,           -- kickoff time (UTC)
    status            VARCHAR,             -- SCHEDULED / IN_PLAY / FINISHED / ...
    home_team_id      INTEGER,             -- -> teams.team_id
    away_team_id      INTEGER,             -- -> teams.team_id
    home_score        INTEGER,             -- full-time goals (NULL until played)
    away_score        INTEGER
);

-- ---------------------------------------------------------------------------
-- standings — league-table snapshots, one row per team per ingest.
-- Source: football-data.org.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS standings (
    fetched_at        TIMESTAMP NOT NULL,
    competition_code  VARCHAR NOT NULL,    -- 'PD' / 'CL'
    season            INTEGER,
    team_id           INTEGER,             -- -> teams.team_id
    position          INTEGER,             -- 1 = top of the table
    played_games      INTEGER,
    won               INTEGER,
    draw              INTEGER,
    lost              INTEGER,
    points            INTEGER,
    goals_for         INTEGER,
    goals_against     INTEGER,
    goal_difference   INTEGER
);

-- ---------------------------------------------------------------------------
-- news — football headlines from RSS feeds, append-only. `url` identifies an
-- article (used to avoid storing the same one twice within a fetch).
-- Source: RSS (Guardian, ESPN FC, ...).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news (
    fetched_at        TIMESTAMP NOT NULL,
    source            VARCHAR,             -- 'Guardian Football', 'ESPN FC', ...
    title             VARCHAR,
    url               VARCHAR,             -- the article link
    published_at      TIMESTAMP,
    summary           VARCHAR
);

-- ---------------------------------------------------------------------------
-- injuries — current injuries/suspensions. May be sparse before the season.
-- Source: API-Football.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS injuries (
    fetched_at        TIMESTAMP NOT NULL,
    team_id           INTEGER,             -- -> teams.team_id
    player_name       VARCHAR,
    type              VARCHAR,             -- e.g. 'Missing Fixture' / 'Questionable'
    reason            VARCHAR,             -- e.g. 'Knee Injury'
    fixture_date      TIMESTAMP            -- the match it relates to (if any)
);

-- ---------------------------------------------------------------------------
-- lineups — starting XIs & formations. Empty until matches are near/played;
-- defined now so ingestion has a home for the data when the season starts.
-- Source: API-Football.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lineups (
    fetched_at        TIMESTAMP NOT NULL,
    match_id          INTEGER,             -- the fixture
    team_id           INTEGER,             -- -> teams.team_id
    formation         VARCHAR,             -- e.g. '4-3-3'
    player_name       VARCHAR,
    player_position   VARCHAR,             -- 'G' / 'D' / 'M' / 'F' or grid position
    is_starter        BOOLEAN              -- TRUE = starting XI, FALSE = bench
);

-- ---------------------------------------------------------------------------
-- predictions — the self-evaluation loop. A row is written BEFORE a match (the
-- companion's call), then filled in with the actual result AFTER (in Phase 4's
-- review), so we can measure honest accuracy over the season.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    created_at            TIMESTAMP NOT NULL,  -- when we logged the prediction (pre-match)
    match_id              INTEGER,             -- football-data.org match id (if known)
    competition_code      VARCHAR,             -- 'PD' / 'CL'
    match_label           VARCHAR,             -- human-readable, e.g. 'Barcelona vs Elche'
    predicted_result      VARCHAR,             -- 'HOME_WIN' / 'DRAW' / 'AWAY_WIN'
    predicted_home_score  INTEGER,
    predicted_away_score  INTEGER,
    confidence            INTEGER,             -- 0–100
    reasoning             VARCHAR,             -- why the companion made this call
    actual_home_score     INTEGER,             -- filled in after the match (NULL until then)
    actual_away_score     INTEGER,
    correct               BOOLEAN              -- filled in after scoring (NULL until then)
);
