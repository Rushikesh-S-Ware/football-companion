# CLAUDE.md — operating rules for this project

> Distilled from the project kickoff. Read this at the start of every session.
> These rules override default behaviour.

## Who I'm working with
- **Rushikesh.** Background: data analytics (strong SQL, moderate Python). NOT a
  confident coder. This project is both a **portfolio piece** and how he learns.
- I write most of the code; he must **understand every decision** well enough to
  defend it in a job interview.
- Explain in **simple English, no unexplained jargon**. After each phase, give a
  plain-English walkthrough: what was built, why, and how data flows through it.

## How we work
- Work strictly in the **phases** below. **HARD STOP** at the end of each phase.
  Never start the next phase until Rushikesh types **"next"**.
- After each walkthrough, ask him questions and have **him** write 3–5 bullets into
  `DECISIONS.md` in his own words. Do **not** write those bullets for him (fix
  grammar at most). That file is his interview prep.
- Small steps. One feature per commit, clear commit messages. If he asks "why",
  answer before writing more code.
- **After every commit:** append an entry to `LEARNING_LOG.md` (I maintain this one,
  in my words) covering **what** we did, **why**, **why not the alternatives**, and
  **how it could be better** — and summarize that same four-part breakdown in chat.
  This is the teaching journal; it is distinct from `DECISIONS.md` (his words, his
  interview prep). Newest entries first.
- **Three things he owns personally** — I draft options + explain trade-offs simply,
  then he chooses and edits the final version himself:
  1. the DuckDB schema (Phase 1)
  2. the companion's system prompt / personality (Phase 3)
  3. the match-note template (Phase 2)
- Windows + PowerShell. Use Windows-friendly commands and paths.

## Do NOT overbuild
Not in the spec? Ask before adding it. **Explicitly OUT of v1** (refuse politely,
remind him it's phase 2): embeddings / vector DB (keyword + recency retrieval
first — embeddings only if retrieval provably fails), Telegram/WhatsApp bot,
Docker, multi-agent, other leagues or sports, ML prediction models, web scraping
beyond RSS, voice.

## What we're building
A **football companion** — an analyst *friend* Rushikesh talks football with,
focused on **La Liga & the Champions League, with FC Barcelona at the center**. It:
- chats about matches, form, stats, tactics, formations, pulling **REAL current
  data through tools** (never invented numbers);
- writes a **pre-match briefing** before matches he cares about (form, head-to-head,
  likely lineups, injuries, tactical angle) and **logs a prediction** (result +
  scoreline + confidence + reasoning);
- after each matchday, **reviews what happened, scores its own predictions**, writes
  match notes, and updates its opinions;
- keeps **persistent memory across the season** (match notes, an opinion log with
  evidence, discussion log) — in March it remembers what it believed in September;
- **listens to Rushikesh's own match observations** and stores them.
Not a generic chatbot. The engineering value = **live data pipeline + memory system
+ self-evaluation loop**. Resume framing: "conversational analyst agent with
persistent memory, tool use over live sports data, and self-evaluating predictions
across a full season."

## How "learning" works here (important)
**No fine-tuning, no retraining, no ML models.** It learns the way an agent learns:
fresh data ingested weekly + written memory + scored predictions + opinions updated
on evidence. If he asks to "train it" / "make it learn for real", point him here.

## Tech stack (decided — do not relitigate)
- Python 3.11+, plain `venv` + `requirements.txt` (pyproject.toml only for the
  editable install so `python -m companion.*` works).
- **Data sources** (VERIFY current free-tier coverage + rate limits in Phase 1
  before building on them):
  - **football-data.org** — fixtures, results, standings (La Liga + UCL).
  - **API-Football** free plan — lineups, formations, injuries, match stats
    (100 req/day: design ingestion to fit, cache everything in DuckDB, never call
    live during chat if data is already cached).
  - **News**: 3–4 reliable football RSS feeds (Guardian, ESPN FC — pick working
    ones in Phase 1) via `feedparser`, stored in DuckDB. He can also paste articles.
  - **xG**: only if a free source fits the above; otherwise v1 lives without it.
- Storage: **DuckDB**, single file in `data/`. Every fetch is a **timestamped
  snapshot — append, never overwrite.**
- **Memory**: human-readable markdown in `memory/` (**committed to git — versioned
  brain**) + a predictions table in DuckDB.
- Agent: **Anthropic Python SDK**, tool-use loop, current Claude Sonnet model
  (confirm ID in Phase 3). Key from `.env` as `ANTHROPIC_API_KEY`. Chat must
  **summarize/trim old turns** so context + cost stay controlled.
- UI: **terminal chat first**; one **Streamlit** page in Phase 4. Tests: **pytest**
  (deterministic parts). Config: python-dotenv. `.gitignore`: `.env`, `data/*.duckdb`.
- README.md with a mermaid diagram, updated every phase. Code style: type hints,
  docstrings, comments explaining **WHY**.

## Memory design (the heart of the project)
- `memory/match_notes/YYYY-MM-DD_barcelona-vs-X.md` — one file per reviewed match,
  using **his template** (result, key stats, tactical observations, his own
  observations, what surprised the companion vs. its prediction).
- `memory/opinions.md` — living takes ("Barça are vulnerable to a high press"), each
  with evidence, date last updated, confidence. **Updated only with a reason** —
  opinions change on evidence, not vibes.
- `memory/discussions.md` — short dated entries appended after each chat: what was
  discussed, anything new he told it, any take that shifted.
- Predictions in a DuckDB table: match, predicted result + scoreline, confidence,
  reasoning, actual result, correct-or-not.
- Retrieval tool: `read_memory(query)` — filename + keyword search, most recent
  first. **Simple on purpose.**

## The companion's character (Phase 3 — HE writes the final prompt, I draft two)
Has opinions and defends them; disagrees when evidence says so (**no yes-man**);
Culé at heart, honest in the head; **every stat must come from a tool call or
memory** — if it doesn't know, it says so; asks him about matches he watched and
records what he says; naturally refers back to things discussed weeks ago.

## Tools the agent gets
`get_fixtures(team_or_competition, next_n)`, `get_results(team_or_competition,
last_n)`, `get_standings(competition)`, `get_team_form(team)`,
`get_lineups_and_injuries(team_or_match)`, `get_news(topic, since)`,
`read_memory(query)`, `write_memory(type, content)`, `log_prediction(...)`,
`score_predictions(matchday)`.

## Commands (the product)
- `python -m companion.chat` — open conversation, tools + memory live.
- `python -m companion.ingest` — pull latest fixtures/results/standings/lineups/news
  into DuckDB.
- `python -m companion.briefing --next-barca` (or `--match "X vs Y"`) — writes
  `briefings/<date>_<match>.md` + logs the prediction.
- `python -m companion.review --since <date>` — scores predictions against results,
  drafts match notes for him to annotate, updates opinions with reasons.
- `python -m companion.stats` — prediction accuracy so far, overall + by competition.

## Evaluation (what makes this serious)
Every prediction is logged **before** the match, scored after. Streamlit (Phase 4)
shows cumulative prediction accuracy over the season, the opinion log, and the
briefing archive. **The honest accuracy number — good or bad — is the point:** it
proves the learning loop is real.

## Phases — HARD STOP after each
- **Phase 0 — Setup.** git init, venv, requirements, .env.example, .gitignore,
  skeleton (`src/companion/`, `tests/`, `memory/`, `briefings/`, `data/`), CLAUDE.md,
  DECISIONS.md, README skeleton. Prove APIs work: print Barcelona's next 5 fixtures
  + current La Liga top 5. STOP.
- **Phase 1 — Data layer.** Verify free-tier coverage of both APIs, then ingest
  fixtures/results/standings (+ lineups/injuries) into DuckDB; RSS news ingestion.
  Schema: show 2 designs with trade-offs; he picks + edits; then implement. 2–3
  pytest tests. STOP.
- **Phase 2 — Memory system.** The `memory/` structure, read/write tools,
  predictions table. He designs the match-note template. Seed `opinions.md` together
  with 3–5 starting takes about Barça's current squad. STOP.
- **Phase 3 — The companion.** Tool definitions, system prompt (propose 2 drafts, he
  edits + approves), `chat` + `briefing` commands, conversation summarization. Dry
  run: a real briefing for Barça's next fixture, prediction logged. STOP.
- **Phase 4 — Learning loop + ship.** `review` + `stats` commands, Streamlit page
  (accuracy chart, opinions, briefing archive), finished README with mermaid +
  screenshots. STOP.

## Definition of done for v1
He can: chat about La Liga using real current data; get a briefing with a logged
prediction before any Barça match; run `review` after a matchday and watch it score
itself, write notes, update opinions; see its season accuracy; and explain every
module in plain English. Everything beyond that is phase 2.

## Current status
- **Phase 1 (data layer): complete.** `ingest` command + 3 tests; football-data.org
  + RSS form the live pipeline (API-Football free tier lacks current-season access —
  parked for phase 2/paid). **Phase 2 (memory system): in progress.** (Pivoted from
  an earlier FPL-manager concept.) Update this line at the end of each phase.
