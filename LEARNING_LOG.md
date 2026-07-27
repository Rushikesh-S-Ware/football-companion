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

## 2026-07-27 · Set up this learning log
**Commit:** _(this one)_

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
