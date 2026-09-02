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

## 2026-07-27 · Grounding fix — the 8b model was inventing facts
**Commit:** _(this one)_

- **What we did:** The Groq switch defaulted to `llama-3.1-8b-instant`, which
  **hallucinated** match results and players instead of calling tools (Rushikesh
  caught it inventing a 5-2 Rayo win and a non-existent player). Reordered the model
  preference to **tool-reliability first** (70b / gpt-oss / kimi / qwen before 8b) and
  appended a **hard runtime guard** to the system prompt (dated; "never state a result
  or player without a tool call; if a tool returns nothing, say so").
- **Why:** Grounding is the project's whole promise — a *fast* model that fabricates is
  worse than a slow honest one. Small models are weak at function-calling and prone to
  confabulation; a bigger tool-reliable model **plus** a blunt rule is the fix.
- **Why not alternatives:** Keeping 8b for speed (broke the golden rule); prompt-only
  (a too-weak model ignores it — you need both a capable model and the rule).
- **How it could be better:** force `tool_choice` for data questions; a per-account
  model capability check; a lightweight eval that flags any un-sourced stat.

---

## 2026-07-27 · Switch Leo's brain to Groq (fast Llama)
**Commit:** `ae6c3b0`

- **What we did:** Rewired the agent from Google Gemini to **Groq**
  (`llama-3.3-70b-versatile`). New `agent.py` drives an **OpenAI-style tool loop by
  hand** (Groq doesn't auto-call): it builds each tool's schema from our functions'
  type hints + docstrings, runs the `tool_calls`, feeds results back, and loops.
  `briefing` uses `agent.generate()` (one-shot); `chat`/`webapp` use
  `agent.send_message()` (returns a string). Deps: `google-genai` → `groq`; key is
  now `GROQ_API_KEY`. Leo's personality, tools, and memory are unchanged.
- **Why:** Gemini's free tier was slow and threw 503s under load; Groq runs Llama on
  very fast hardware (free tier), so replies come back much quicker. Only the *engine*
  changed — the model is one constant, so swapping providers stays easy.
- **Why not alternatives:** Cerebras / Mistral (similar; Groq is fastest + has the
  clearest tool-use docs); staying on Gemini (too slow for real use).
- **How it could be better:** Llama is a touch less nuanced than Gemini/Claude on
  subtle reasoning (fine for grounded tool-chat); stream replies; add a thin
  provider-abstraction so the swap is a single flag.

---

## 2026-07-27 · Faster cold start — light load for the web app
**Commit:** `2a3df17`

- **What we did:** `run_ingest(light=True)` fetches **only La Liga** (skips Champions
  League matches + RSS news); the web app's cold-start now uses it. Verified: light
  load = 2 API calls (PD matches + standings + teams) vs the full ~570 matches + 3 feeds.
- **Why:** On a fresh cloud host the app was pulling *everything* before showing the
  page — the slowest moment. La Liga + Barça covers most chat; the full `ingest`
  command still gets UCL + news.
- **Why not alternatives:** committing a pre-built data snapshot (binary + goes stale);
  no ingest at all (then the data tools return nothing).
- **How it could be better:** stream Leo's replies (feels faster per message); the
  free-tier machine + LLM are the real ceiling — local run or a small paid tier removes it.

---

## 2026-07-27 · Auto-retry transient Gemini errors (429 / 503)
**Commit:** `6245904`

- **What we did:** Added `agent.send_message()` — it retries transient free-tier
  errors (429 rate limit, **503 "high demand"/overloaded**, 500) with 3s → 6s → 9s
  backoff, and wired it into the web + terminal chat with a clearer message.
- **Why:** The free Gemini tier intermittently returns **503** (Google's servers
  overloaded — not our quota); a few-second retry usually clears it, so most hiccups
  now self-heal instead of failing the message.
- **Why not alternatives:** Leaning on the SDK's built-in retries (didn't cover this);
  a paid tier (removes deprioritization, but costs money).
- **How it could be better:** backoff with jitter; a model fallback; streaming replies
  so the waits feel shorter.

---

## 2026-07-27 · Web chat — talk to Leo in a browser
**Commit:** `18538ec` (+ `48a9cad` deploy-ready)

- **What we did:** `webapp.py` — a Streamlit **web chat** (`st.chat_input` /
  `st.chat_message`) that reuses the *same* agent (Gemini + tools + system prompt) and
  the *same* memory as the terminal chat, with a sidebar showing live accuracy + Leo's
  opinions and a "💾 Save chat to memory" button. Verified in-browser: renders, accepts
  input, Leo processes.
- **Why:** The platform is just a front door — the chat plugs into Leo's existing brain
  (agent + memory), so there was nothing new to build there; Streamlit turns a Python
  script into a browser chat. Saved chats + memory work identically to the terminal.
- **Why not alternatives:** A native mobile app (huge, off our Python/Streamlit stack) —
  a *deployed* web page opens in a phone browser and can be "added to home screen,"
  covering the mobile need pragmatically. WhatsApp/Telegram bots stay a v2 idea.
- **How it could be better:** Deploy to Streamlit Community Cloud / Hugging Face Spaces
  for a public URL (phone access) — needs the shared-key + data-on-host wrinkles sorted;
  stream Leo's reply token-by-token.

---

## 2026-07-27 · Dashboard + finished README — v1 shipped 🏁
**Commit:** `badd593`

- **What we did:** `dashboard.py` — a one-page Streamlit app (accuracy metrics +
  cumulative-accuracy chart + Leo's opinions + the briefing archive). Verified it
  renders in a browser (showed 1/1, 100%). Rewrote `README.md` as the finished v1
  (commands, setup with the Gemini + football-data keys, mermaid, memory design,
  free-tier note) and added a `screenshots/` folder. **Phases 0–4 done — v1 shipped.**
- **Why:** The dashboard is a read-only view over the DB + memory files (no API) —
  it turns the honest accuracy number, the opinion log, and the briefings into one
  shareable page. The README is the portfolio front door.
- **Why not alternatives:** A heavier web framework (Streamlit makes a dashboard from
  a plain Python script); deploying to a public host (out of v1 scope — easy later).
- **How it could be better:** a per-competition accuracy bar, confidence calibration,
  a real screenshot committed, and a public deploy (e.g. Hugging Face Spaces).

---

## 2026-07-27 · The learning loop — review + stats commands
**Commit:** `b995c81`

- **What we did:** `review.py` (scores predictions against results, drafts a match note
  per scored game) + `stats.py` (accuracy overall + by competition), backed by
  `score_predictions` / `accuracy_stats` in `predictions.py`, plus 2 tests. **Demo:**
  since the new season hasn't started, we **backtested** — logged a prediction for
  Barça's real 2-1 win at Atlético; `review` scored it ✅ correct; `stats` shows 1/1.
- **Why:** Scoring is fully **deterministic** (no API) — just compare the logged
  prediction to the stored result. Backtesting against last season's real results
  (already in the DB) proves the loop today without waiting for August.
- **Why not alternatives:** (1) Auto-editing `opinions.md` — rejected: opinions must
  change *deliberately, with a reason*, so review **surfaces** the evidence and a
  human/Leo updates the take thoughtfully, rather than a script rewriting beliefs.
  (2) Using Leo/the API to score — unnecessary; it's pure comparison.
- **How it could be better:** Match prediction↔result by `match_id` (sturdier than
  parsing the label); confidence-weighted scoring (Brier score); a Leo-assisted
  "which opinions should shift?" suggestion after each review.

---

## 2026-07-27 · Briefing command + dry run — Phase 3 done
**Commit:** `28a990d`

- **What we did:** Built `briefing.py` (`python -m companion.briefing --next-barca`).
  It gathers the facts itself (form, standings, news, memory), asks Leo for the whole
  briefing in **one** Gemini call, parses the structured prediction block, saves
  `briefings/<date>_<match>.md`, and logs the prediction. **Dry run:** Leo wrote a real
  Elche vs Barça briefing and logged **AWAY_WIN 0-2 (80%)**.
- **Why:** One call instead of ~8 tool round-trips keeps us under the free-tier limit;
  a deterministic regex parse of a fixed prediction block avoids a second call. We
  **verified grounding**: every stat Leo cited (94 pts, 13th, the 7-2 Newcastle and
  2-1 Atleti form) traced back to the DB, and he *refused* to invent head-to-head. The
  golden "never invent" rule held.
- **Why not alternatives:** Letting Leo tool-call his own data for a briefing (would
  429 instantly); free-text prediction parsing (a fixed block is far more reliable).
- **How it could be better:** The prediction parse depends on Leo following the format
  (fallback: it just isn't logged); could use Gemini structured output; real multi-season
  head-to-head once we store more than the current snapshot.

---

## 2026-07-27 · Leo can talk — chat command + tools on Gemini
**Commit:** `e32de8b`

- **What we did:** Built the companion. `system_prompt.md` (Leo's personality —
  Rushikesh's Artifact #3), `queries.py` (read fixtures/results/standings/form/news
  from DuckDB), `tools.py` (Leo's tool set + read/write memory + log_prediction),
  `agent.py` (Gemini client + system prompt + tools), and `chat.py`
  (`python -m companion.chat`). **Verified:** Leo pulled Barça's real next fixtures
  via a tool call and replied in character.
- **Why:** Gemini's *automatic function calling* runs our Python tool functions for
  us — no hand-written tool loop. The model is one constant (`gemini-flash-latest`)
  so switching provider/model later is a one-line change. Tools read the latest
  DuckDB snapshot (never the live API), matching the cache-everything design.
- **Why not alternatives:** A manual tool loop (the SDK does it); calling live APIs
  from chat (rate limits — we read the cached DB instead).
- **KEY FINDING / how it could be better:** The Gemini **free-tier rate limit is
  tight** — a couple of tool-using messages returned `429 RESOURCE_EXHAUSTED`. The
  chat handles it gracefully (session stays alive). Real use needs pacing between
  messages, or a small paid tier (one-line model swap). Conversation compaction is
  basic (summarize + restart every 12 turns) — could be smarter later.

---

## 2026-07-27 · Decision: use Google Gemini free tier for the agent
**Commit:** `a111d30`

- **What we did:** Recorded a stack change in `CLAUDE.md` — the Phase 3 companion will
  run on the **Google Gemini free tier** (`google-genai`, a Gemini Flash model),
  not the Anthropic/Claude Sonnet the spec originally named.
- **Why:** Cost. Rushikesh wanted $0 over the ~$2–5/month Claude estimate. Gemini's
  free tier supports function calling, so the tool-use agent is still buildable.
- **Why not the alternative:** Paid Claude was cheap and slightly stronger at nuanced
  tool-use/debate, but "free with an acceptable trade-off" won for a personal project.
  The deliberate cost decision is itself a good interview story.
- **How it could be better:** Free-tier rate limits + Google may use free-tier inputs
  to improve products; a later paid tier (Claude or Gemini paid) removes both. We keep
  the model wiring as one config value in Phase 3 so switching providers stays easy.

---

## 2026-07-27 · Memory tools + predictions table (Phase 2 core)
**Commit:** `94da7ee`

- **What we did:** Added `memory.py` (`read_memory` / `write_memory`), `predictions.py`
  (`log_prediction` / `get_predictions`), the `predictions` table in `schema.sql`,
  `discussions.md`, and 4 tests. `read_memory` does keyword + most-recent-first search
  over the markdown brain; `write_memory` appends/creates the right file; predictions
  are stored **before** a match.
- **Why:** These are the exact tools the Phase 3 agent will call to remember and
  record. `read_memory` is **deliberately simple** (keyword + recency) per the spec —
  it's explainable and enough for a small brain. Logging predictions pre-match is what
  keeps the season accuracy number honest (we can't rewrite history after the fact).
- **Why not alternatives:** (1) Embeddings / vector DB for retrieval — rejected for v1:
  overkill for a handful of markdown files, and a keyword search is easy to explain in
  an interview. We only add embeddings if this *provably* fails. (2) Storing opinions/
  notes in DB tables — rejected: markdown in git is human-readable *and* versioned (you
  can `git diff` how an opinion changed over the season).
- **How it could be better:** `read_memory` scoring is naive term-counting (could weight
  title hits, or rank by date-in-filename); `write_memory("opinion")` only appends
  (could update a specific take in place). Good enough now; revisit if retrieval feels weak.

---

## 2026-07-27 · Match-note template (Artifact #2) + start Phase 2
**Commit:** `4deed23`

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
