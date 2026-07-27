# LEARNING_LOG.md — the teaching journal

> **Maintained by Claude, written for Rushikesh.** After every commit I add an entry
> here explaining, in plain English:
> - **What we did** — the change, in one breath.
> - **Why we did it this way** — the reasoning.
> - **Why not the alternatives** — what else we considered, and why we passed.
> - **How it could be better** — what a more advanced version would do later.
>
> This is different from `DECISIONS.md` (which *you* write in your own words for
> interview prep). This file is the "here's what a mentor would tell you" log — read
> it to learn, and to keep the project honest about its own trade-offs. Newest first.

---

## 2026-07-27 · Match-note template (Artifact #2) + start Phase 2
**Commit:** _(this one)_

- **What we did:** Added `memory/match_notes/_TEMPLATE.md` — the form the companion
  fills in per reviewed match. Rushikesh chose a **blend** of structured stats +
  narrative reflection, and approved it. Marked Phase 1 complete.
- **Why:** A consistent note format makes match memories scannable *and* reflective.
  Two deliberate sections: "What I saw (my own eyes)" captures Rushikesh's human
  observations, and "Did it change my mind?" links a match to an `opinions.md` update
  — that link is what closes the learning loop (evidence → belief change, with a reason).
- **Why not alternatives:** Pure-structured (option A) was fast to fill but shallow;
  pure-narrative (option B) was rich but inconsistent to scan/query later. The blend
  keeps both.
- **How it could be better:** Later, auto-fill the result/stats from the DB so he only
  writes the human parts (what he saw, whether it changed his mind).

---

## 2026-07-27 · Built the data layer (ingest command + tests)
**Commit:** `39124b6`

- **What we did:** Added `db.py` (DuckDB helpers), `sources.py` (fetch + parse for
  football-data.org, API-Football, RSS), `ingest.py` (the `python -m companion.ingest`
  command), and 3 tests. First real ingest landed **569 matches, 56 standings rows,
  54 teams, 164 news items** as timestamped snapshots.
- **Why:** Split the code into FETCH (talks to the network), PARSE (pure functions),
  and STORE (database) so the deterministic bits are unit-tested with fake data and no
  network. Every row is stamped `fetched_at` (append-only). Each source is wrapped in
  its own try/except so one failure (e.g. a rate limit) doesn't sink the whole run.
- **Why not alternatives:** (1) Calling the APIs *live during chat* — rejected: rate
  limits (football-data.org = 10/min). We cache into DuckDB and read from there.
  (2) One big module — rejected: separating fetch/parse/store is what makes the parse
  functions testable and the code readable.
- **KEY FINDING + how it could be better:** The API-Football **free plan can't access
  the current season** (only ~2022–2024), so live lineups/injuries aren't available.
  We turned it OFF by default (`INGEST_API_FOOTBALL=1` to re-enable) and park it for
  phase 2 / a paid plan — the companion will get injury context from news + pasted
  notes instead. Future polish: retry/backoff, de-dupe news by URL across snapshots,
  add foreign-key constraints, and (if ever needed) build the team bridge from an
  accessible season (2024) since API-Football team ids are stable across seasons.

---

## 2026-07-27 · Chose the data-layer schema (Design B, normalized)
**Commit:** `026a3e7`

- **What we did:** Added `src/companion/schema.sql` — the DuckDB data model.
  Design B (**normalized**): a `teams` reference table storing both APIs' ids for the
  same club, plus **append-only snapshot** tables (`matches`, `standings`, `news`,
  `injuries`, `lineups`), each stamped with `fetched_at`.
- **Why:** Our two sources name *and* id the same club differently (Barça = 81 on
  football-data.org, 529 on API-Football). Normalizing teams once makes every later
  join reliable. Append-only (never overwrite) is what gives the companion its
  season-long memory.
- **Why not alternatives:** Design A (team names stored as plain text) was fewer
  tables and no joins, but cross-source joins would be fragile (spelling mismatches).
  Rushikesh — strong in SQL — chose B; joins are his home turf and it's the stronger
  portfolio story.
- **How it could be better:** Could add explicit foreign-key constraints, a surrogate
  `snapshot_id`, or split `matches` into static-info + score-snapshot tables if
  storage grows. Kept lean for now; revisit only if a real need appears.

---

## 2026-07-27 · Closed Phase 0 (live API proof + recorded decisions)
**Commit:** `5944968`

- **What we did:** Ran the smoke test against the *real* football-data.org API (got
  Barça's actual upcoming fixtures + the La Liga table), Rushikesh wrote his Phase 0
  bullets in `DECISIONS.md` (I fixed grammar/typos only), and marked Phase 0 complete.
- **Why:** A phase isn't "done" until the proof runs on real data *and* the reasoning
  is captured in his own words. I deliberately only fixed grammar — rewriting his
  bullets would make them mine, and useless to defend in an interview.
- **Why not alternatives:** I *could* have authored the two missing bullets (venv,
  secret-safety) for him. Held the line — the project rules say "fix grammar at most"
  for exactly this reason.
- **How it could be better:** The standings call returned *last season's* final table
  (the new season hasn't kicked off). Phase 1 should detect season boundaries so
  "current standings" means the live season once matches are played.

---

## 2026-07-27 · Set up this learning log
**Commit:** `15254f3`

- **What we did:** Added `LEARNING_LOG.md` and made "update it after each commit" a
  standing rule in `CLAUDE.md`.
- **Why:** Writing down *why* a decision was made — and what we rejected — is how you
  turn "I followed a tutorial" into "I can defend my architecture." It also keeps me
  (Claude) accountable: every choice now has to survive being written down.
- **Why not alternatives:** We could have kept everything in `DECISIONS.md`, but that
  file is *your* voice for interviews; mixing my detailed rationale into it would
  drown out your bullets. Two files, two jobs.
- **How it could be better:** Later we could auto-generate a first draft of each entry
  from the commit diff, then I refine it. For now, hand-written keeps it thoughtful.

---

## 2026-07-27 · Pivot from FPL manager → Football Companion
**Commit:** `f954583`

- **What we did:** Replaced the Fantasy-Premier-League scaffolding with the Football
  Companion project (Barça/La Liga analyst friend), all in **one coherent commit**.
- **Why:** The two projects share tooling (Python, venv, DuckDB, the Anthropic SDK)
  but differ in *domain, package name (`fpl_agent` → `companion`), and data sources*.
  Doing the pivot as a single atomic commit gives the git history a clean "before →
  after" story instead of a confusing half-and-half state.
- **Why not alternatives:**
  - *Start a brand-new repo* — you'd lose the setup history and re-do config. Reusing
    the folder (which isn't in OneDrive, so no sync issues) was simpler.
  - *Wipe git history for a clean start* — you chose to keep it. The honest record of
    "we tried FPL, then pivoted" is a fine story and preserves the learning trail.
  - *Many tiny commits for the pivot* — for a sweeping rename, one atomic commit is
    easier to read and safer to revert.
- **How it could be better:** For files that were truly *renamed* (not rewritten) we
  could have used `git mv` to preserve per-file history/blame. Here the content
  changed so much it didn't matter, but it's the cleaner habit when it applies.

---

## 2026-07-27 · Project scaffolding (venv, layout, safety rails)
**Commits:** `ee33e1c` (initial) + carried into `f954583`

- **What we did:** Created a virtual environment, `requirements.txt`, a **src/ layout**
  (`src/companion/`), a minimal `pyproject.toml` for an **editable install**, a
  `.gitignore` that blocks `.env` and `data/*.duckdb`, and a `.env.example` template.
- **Why:**
  - **venv** = a private box of libraries just for this project, so it never clashes
    with other Python on your machine.
  - **src/ layout + editable install** = clean imports. `python -m companion.chat`
    works, and Python can't accidentally import our half-built package before it's
    installed (a real bug source with the "flat" layout).
  - **.gitignore for secrets** = the #1 way people leak API keys is committing `.env`.
    We closed that door on day one. Only the blank `.env.example` is tracked.
- **Why not alternatives:**
  - *conda / Poetry / pipenv instead of venv* — heavier, extra tooling to learn; the
    spec said "plain venv", and built-in is one less thing to break.
  - *Flat layout (package at repo root)* — simpler, but hides import mistakes and is
    considered less professional. src/ is the modern standard.
  - *Pinning exact versions (`==`)* — we used floors (`>=`) so a fresh install just
    works. Trade-off: less perfectly reproducible (see "better" below).
- **How it could be better:** Add a **lock file** (via `pip-tools` or `uv`) so every
  install gets identical versions — real reproducibility. Add `pre-commit` hooks for
  auto-formatting/linting, and a CI check later. Overkill for now; noted for when the
  project grows.

---

## 2026-07-27 · API smoke test with friendly failure
**File:** `src/companion/check_api.py` (in `f954583`)

- **What we did:** A tiny script that fetches Barça's next 5 fixtures + the La Liga
  top 5 from football-data.org. If the API key isn't set yet, it prints clear setup
  steps instead of crashing. Also forced stdout to UTF-8 so Spanish names
  ("Atlético") render on Windows.
- **Why:** **De-risk early.** Before building a whole data layer on an API, prove in
  20 lines that the network path and auth work. A friendly "no key yet" message is
  kinder to a learner (and to anyone who clones the repo) than a stack trace.
- **Why not alternatives:**
  - *Put the key in the URL* — never. Secrets in URLs get logged and cached. We send
    it in the `X-Auth-Token` **header** instead.
  - *Crash on missing key* — technically fine, but confusing. The guard-and-explain
    pattern teaches the user what to do next.
  - *Look up Barcelona's team id dynamically* — for a one-off proof, hardcoding id
    `81` is fine and clear. The real Phase 1 data layer will resolve names → ids properly.
- **How it could be better:** Add **retry with backoff** for flaky networks, respect
  the API's **rate limits**, and validate the token with one cheap call so a *wrong*
  key (not just a missing one) gives a clear error. All Phase 1 concerns.
