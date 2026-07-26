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
- **Two things he owns personally** — for each, present 2 options with trade-offs
  in simple terms, then he chooses and edits the final version himself:
  1. the DuckDB schema (Phase 1)
  2. the agent's system prompt (Phase 3)
- Windows + PowerShell. Use Windows-friendly commands and paths.

## Do NOT overbuild
Not in the spec? Ask before adding it. **No** Docker, Kubernetes, microservices,
multi-agent, or ML models in v1 — even if he gets excited mid-build and asks.
Remind him of the "Definition of done" and push back politely. Refuse scope creep
like StatsBomb data, live match features, or other sports — that's "phase 2".

## What we're building
An autonomous FPL manager. Each gameweek it: pulls live FPL data → projects player
points with a transparent formula → optimizes the squad under official FPL rules →
applies LLM judgment (injuries, rotation, pasted news) → outputs a recommendation
report (transfers, captain, bench order) with written reasoning. Rushikesh submits
picks manually on the FPL website — **the program never logs into his FPL account.**

## Tech stack (decided — do not relitigate)
- Python 3.11+, plain `venv` + `requirements.txt` (pyproject.toml only for the
  editable install so `python -m fpl_agent.*` works).
- Data: official FPL API, read-only, no auth. Base `https://fantasy.premierleague.com`.
  Endpoints: `/api/bootstrap-static/`, `/api/fixtures/`, `/api/element-summary/{id}/`.
- Storage: **DuckDB**, single file in `data/`. Every fetch is a **timestamped
  snapshot — append, never overwrite** (so we can backtest later).
- Optimizer: **PuLP** (linear programming).
- Agent: **Anthropic Python SDK**, tool-use loop, current Claude Sonnet model
  (confirm model ID with him in Phase 3). Key from `.env` as `ANTHROPIC_API_KEY`.
- UI: **Streamlit**, one page. Tests: **pytest** (deterministic parts only).
- Config: python-dotenv. `.gitignore` must include `.env` and `data/*.duckdb`.
- README.md with a mermaid architecture diagram, updated at the end of every phase.
- Code style: type hints, docstrings, small functions, comments explaining **WHY**.

## FPL rules the optimizer must enforce
£100.0m budget; 15 players = 2 GK / 5 DEF / 5 MID / 3 FWD; max 3 per real club;
each GW a valid starting XI (1 GK, 3–5 DEF, 2–5 MID, 1–3 FWD); captain (2x) +
vice; bench order. Free transfers: 1/week + banking; extra transfers −4 pts each.
**CONFIRM current 2026/27 rules (incl. banking cap) from official help pages in
Phase 2** and encode them in one `rules.py` as constants with a source comment.
Chips (Wildcard, Bench Boost, Triple Captain, Free Hit) are **OUT of v1 logic** —
the agent may only mention "consider your wildcard" in prose.

## Points projection (v1 = transparent formula, NO ML)
`expected_points(player, gw)` from: recent form (last 4–6 GW PPG blended with
season PPG), minutes/availability probability, fixture difficulty (FDR / team
strength), home/away. All weights in one commented constants block. Must be
explainable in one paragraph. Season start: fall back to last season PPG + price band.

## The agent (Phase 3)
Tool-use loop with tools: `get_gameweek_state`, `get_top_players(position, metric, n)`,
`get_player_detail(name)`, `get_fixtures(team, next_n)`, `run_optimizer(...)`,
`get_my_squad`, plus a free-text notes input for pasted news.
Weekly: `python -m fpl_agent.weekly --gw N` → agent reasons over optimizer output +
data + notes → writes `reports/gw_N.md` (transfers with −4 hit math, captain + vice,
bench order, top 3 risks, "optimizer wanted vs. what I decided and why"). Log every
run to DuckDB: inputs, outputs, model, tokens, cost.

## Evaluation (Phase 4)
Post-GW eval fetches actual points; store three tracks: (a) agent's team,
(b) "do nothing" (GW1 optimizer squad, never touched), (c) "pure optimizer"
(follows optimizer weekly, no LLM). Streamlit charts cumulative points for all three
plus his human team (entered manually). Also store per-player projection error.

## Phases — HARD STOP after each
- **Phase 0 — Setup.** git init, venv, requirements, .env.example, .gitignore,
  folder skeleton, CLAUDE.md, DECISIONS.md, README skeleton. Prove API works with a
  tiny script printing the 5 most expensive players. STOP.
- **Phase 1 — Data layer.** Fetch + snapshot bootstrap-static and fixtures into
  DuckDB. Schema: show 2 designs with trade-offs; he picks + edits; then implement.
  A snapshot CLI command. 2–3 pytest tests. STOP.
- **Phase 2 — Projection + optimizer.** rules.py (confirm current rules first),
  projection module, PuLP optimizer, CLI printing best 15 / XI / captain / cost /
  projected points. Tests: budget, position counts, max-3-per-club. STOP.
- **Phase 3 — Agent.** Tool definitions, system prompt (propose 2 drafts, he edits +
  approves), weekly run command, markdown report, run logging. Dry run. STOP.
- **Phase 4 — Eval + UI + ship.** Post-GW eval command, Streamlit page, finished
  README with mermaid + screenshots, Hugging Face Spaces deploy instructions. STOP.

## Definition of done for v1
He can run three commands — **snapshot, weekly, eval** — get a readable weekly
report, see the comparison chart in Streamlit, and explain every module in plain
English. Nothing else belongs in v1.

## Current status
- **Phase 0: in progress.** (Update this line at the end of each phase.)
