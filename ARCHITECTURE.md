# FPL Manager Agent — Technical Architecture (v1)

> A plain-English deep-dive. If you can explain this document out loud, you can
> defend this project in any interview. Read it top to bottom once; then use the
> glossary at the end when a word is fuzzy.

---

## 1. The one-sentence version

> A program you run once a week that **downloads live FPL data, does the math to
> pick a legal squad, asks an AI to sanity-check that squad with real-world
> judgment, and writes you a report** — then quietly keeps score all season so we
> can prove it works.

Everything below is just that sentence, zoomed in.

---

## 2. Follow one player through the whole machine

Let's follow **Bukayo Saka** through a single weekly run. This is the entire system:

```
   ┌─────────────┐
   │  FPL API    │   "Saka: price £9.5m, 157 pts, played 88 min last game,
   │ (internet)  │    next fixture vs Fulham (home), team-strength 4/5..."
   └──────┬──────┘
          │  (1) FETCH  — download the raw numbers
          ▼
   ┌─────────────┐
   │   DuckDB    │   Save a stamped copy: "as of Sat 2pm, Saka looked like this."
   │ (data file) │   We NEVER overwrite. Every week is kept.
   └──────┬──────┘
          │  (2) READ back the latest snapshot
          ▼
   ┌─────────────┐
   │ Projection  │   A transparent formula turns raw stats into ONE number:
   │  (formula)  │   "Saka is worth ~5.8 expected points this week."
   └──────┬──────┘
          │  (3) every player now has an expected-points score
          ▼
   ┌─────────────┐
   │  Optimizer  │   PuLP tries legal 15-man squads and picks the one with the
   │   (PuLP)    │   highest total expected points, under all the FPL rules.
   └──────┬──────┘   "Best squad includes Saka. Captain: Haaland."
          │  (4) a mathematically optimal, rules-legal squad
          ▼
   ┌─────────────┐   The AI reads the optimizer's answer + the data + YOUR notes
   │ Claude      │   ("Saka rested in midweek, might be rotated"). It reasons:
   │ agent       │   "Optimizer loves Saka, but rotation risk — flag it."
   │ (tool-loop) │
   └──────┬──────┘
          │  (5) judgment applied on top of the math
          ▼
   ┌─────────────┐
   │ reports/    │   A markdown file: transfers, captain, bench order, top risks,
   │ gw_N.md     │   and "what the optimizer wanted vs. what I recommend and why."
   └──────┬──────┘
          │  (6) you read it, you submit picks manually on the FPL site
          ▼
   ┌─────────────┐
   │  Streamlit  │   A one-page dashboard: your squad, the report, and a chart of
   │  dashboard  │   how the agent is doing vs. baselines all season.
   └─────────────┘
```

That's it. Six steps, one direction, once a week. No magic — each box does one
small, understandable job and hands off to the next.

---

## 3. The four layers (and why they're separated)

We deliberately split the program into four **layers**. A layer is just "a group
of code with one responsibility that doesn't care how the other layers work
inside." Separation means we can **test, fix, or replace one layer without
touching the others** — the single most important idea in this whole design.

| # | Layer | Its one job | Built with | Can we unit-test it? |
|---|-------|-------------|------------|----------------------|
| 1 | **Data** | Get FPL numbers, store stamped copies | `requests` + DuckDB | Yes |
| 2 | **Decision** | Turn numbers into a legal best squad | formula + PuLP | Yes (it's pure math) |
| 3 | **Agent** | Add human-style judgment | Claude tool-loop | No (judgment isn't math) |
| 4 | **Presentation** | Show the result | markdown + Streamlit | Not needed |

> **Interview gold:** "Layers 1 and 2 are *deterministic* — same input always gives
> the same output — so I unit-test them with pytest. Layer 3 is *probabilistic*
> judgment, so I evaluate it against baselines over time instead of unit-testing
> it." That one sentence shows you understand *how to test different kinds of code*.

---

## 4. Each component, in plain terms

### 4.1 The Data Layer — "download and remember"

**What it does:** calls three read-only FPL web addresses and saves what comes back.

- `/api/bootstrap-static/` → the big bundle: every player, price, points, team,
  and the gameweek calendar.
- `/api/fixtures/` → the match schedule and difficulty ratings.
- `/api/element-summary/{player_id}/` → one player's game-by-game history.

**Why "read-only" matters:** we only ever *download*. The program has no way to log
into your FPL team or change anything. That's a safety boundary, on purpose.

**The key design choice — append-only snapshots:**
Instead of keeping "the current data" and overwriting it each week, we save a
**new stamped copy every time** and never delete the old ones.

> Think of it like taking a **photograph** of the data each week instead of a
> **live mirror**. A mirror only shows *now*; photographs let you look back.

Why bother? Because in Phase 4 we need to ask *"what did the world look like the
moment we made our decision?"* to score ourselves honestly. You can't answer that
if you overwrote the past. This also unlocks **backtesting** later (replaying old
weeks to test new ideas) — and it's the raw fuel a future ML model would train on.

### 4.2 The Projection — "turn many numbers into one number"

The optimizer can't weigh "he's in form but has a hard fixture" — it needs a
single score per player. The projection produces that: **expected points for the
upcoming gameweek**, one number per player.

It blends four honest ingredients, each with a weight you can see and change:

1. **Recent form** — points per game over the last 4–6 weeks, blended with the
   season average (so one lucky week doesn't fool it).
2. **Playing time** — a player who might be benched or injured gets scaled down.
   No minutes = no points, so this matters a lot.
3. **Fixture difficulty** — playing a weak team is worth more than playing a strong
   one (this is the FDR / team-strength rating).
4. **Home or away** — a small home-advantage nudge.

> **Hard rule (and a feature, not a limitation):** the whole formula must be
> **explainable in one paragraph**. We chose a transparent formula over a black-box
> ML model *on purpose* — "I can tell you exactly why my agent rated Saka 5.8"
> beats "a neural net said so" in every interview.

### 4.3 The Optimizer — "the math brain"

This is the part people find impressive, so understand it well. It solves a
**constrained optimization** problem using **linear programming** (the `PuLP`
library). Big words, simple idea:

> **Goal:** pick the 15 players with the highest *total* expected points.
> **Constraints (the rules it is physically unable to break):**
> - spend ≤ £100.0m
> - exactly 2 GK, 5 DEF, 5 MID, 3 FWD
> - no more than 3 players from any one real club
> - a valid starting XI and formation

Instead of you eyeballing thousands of combinations, PuLP explores them
mathematically and returns the provably best legal squad in a fraction of a
second. It's the same family of tool that airlines use to schedule crews.

> **Why this is the "serious" part:** anyone can call an AI API. Combining an AI
> with a *real optimizer that guarantees the rules* is what makes this an
> engineering project, not a chatbot wrapper.

### 4.4 The Agent — "the judgment brain"

Now the interesting bit: the optimizer is *great at math but blind to the news*.
It doesn't know a player is "doubtful", or rested in midweek, or that his manager
rotates in cup weeks. That's what the **Claude agent** adds.

**How it actually works — the "tool-use loop":**
The AI is not just handed a blob of text. It's given a set of **tools** (small
functions it can call) and it decides which to call, like a person using a search
box:

- `get_gameweek_state()` — what week is it, deadlines, etc.
- `get_top_players(position, metric, n)` — "show me the top 5 midfielders by form"
- `get_player_detail(name)` — one player's full picture
- `get_fixtures(team, next_n)` — upcoming matches for a team
- `run_optimizer(...)` — run the math brain and see its answer
- `get_my_squad()` — what you currently own
- **plus your free-text notes** — where you paste this week's injury/press news

The loop: the AI thinks → calls a tool → reads the result → thinks again → calls
another tool → ... → finally writes the report. It's "agentic" because *it* chooses
the steps; we don't script them.

> **The division of labor to memorize:**
> **Optimizer = what's mathematically best. Agent = what's actually wise.**
> The report even has a section: *"what the optimizer wanted vs. what I decided and
> why"* — that honesty is the whole point.

### 4.5 Presentation — "the human handoff"

Two outputs:
- **`reports/gw_N.md`** — the written recommendation you read each week (transfers
  with the −4-point hit math shown, captain + vice, bench order, top-3 risks).
- **Streamlit dashboard** — one web page showing your squad, the latest report, and
  the season-long score chart.

You stay **in the loop**: the program recommends, *you* decide and submit. That's a
deliberate design choice, not a missing feature.

---

## 5. The two loops that make it "learn" (the honest way)

People hear "learn" and think ML. This system genuinely improves over the season
**without** ML, through two loops:

### Loop A — the weekly adaptation loop (runs every gameweek)
```
fresh data  →  project  →  optimize  →  agent judges  →  report  →  you play
```
Because it **re-downloads reality every single week**, it's always current. When
football evolves — new form, new injuries, new fixtures — the agent sees the
change on the next run automatically. *It adapts by re-reading the truth, not by
memorizing.*

### Loop B — the evaluation / feedback loop (runs after each gameweek)
```
actual points come in  →  compare to what we projected  →  store the error
```
Every week we record **projected vs. actual** for every player. Two payoffs:
1. We can *tune the formula weights with evidence* — real learning you can explain.
2. That error log is **exactly the training data** a future ML model (v2) would
   need. v1 isn't the "dumb" version — it's the version that *earns* the ML version.

We keep **three score-tracks** to prove the agent is actually adding value:
- **(a) the agent's team** — our full system.
- **(b) "do nothing"** — the week-1 optimizer squad, never touched again.
- **(c) "pure optimizer"** — follow the math brain every week, no AI judgment.
- *(plus your human team, entered manually)*

If track (a) beats (b) and (c) over the season, the AI's judgment is *measurably*
worth something. That's the difference between "I built an AI thing" and "I built
an AI thing **and proved it works**."

---

## 6. Why each technology was chosen (defend these)

| Choice | Why (the short version) |
|--------|-------------------------|
| **Python** | The default language for data + AI; huge library support. |
| **FPL API** | Free, official, read-only, no login. The safest possible data source. |
| **DuckDB** | A database that lives in **one file** — no server to run. Feels like SQL (your strength), perfect for stamped snapshots and analytics. |
| **PuLP** | A mature linear-programming library — lets us *guarantee* the FPL rules mathematically rather than hoping our code got them right. |
| **Anthropic SDK** | Gives us the tool-use loop cleanly; Claude is strong at reasoning over messy real-world context. |
| **Streamlit** | Turns a Python script into a web dashboard with almost no web code. |
| **pytest** | Standard testing tool; we point it only at the deterministic math. |
| **A monolith, run locally** | One user, once a week — servers/Docker/microservices would be pure overhead. *Matching the architecture to the problem size is a senior-engineer signal.* |

---

## 7. What v1 is deliberately NOT (and where it goes next)

**Not in v1 (on purpose):** machine-learning models, tactical/formation data
(needs paid StatsBomb/Opta feeds), chips logic (Wildcard etc.), multi-agent
scouting, auto-submitting to FPL.

**The v2 story this sets up** (your headline for interviews):
> "I started with a **transparent baseline** and instrumented it to log its own
> error all season. That gave me the data to later **train an ML model and prove it
> beat the baseline** — a measured improvement, not a guess."

You cannot tell that story without building v1 first. That's why we build v1 first.

---

## 8. Glossary (plain definitions)

- **API** — a web address that hands back data when you ask. Ours only lets us read.
- **Snapshot** — a stamped, saved copy of the data at one moment; we never overwrite.
- **Append-only** — we only ever *add* rows, never edit or delete. Keeps full history.
- **Deterministic** — same input → same output every time (the math parts). Testable.
- **Projection / expected points** — one predicted score per player for the week.
- **Constraint** — a rule the optimizer physically cannot break (budget, positions…).
- **Linear programming / optimization** — math that finds the best option under rules.
- **Tool-use loop / agent** — an AI that chooses which functions to call, step by
  step, to reach an answer (instead of us scripting every step).
- **Baseline** — a simple strategy we compare against to prove our system adds value.
- **Backtest** — replaying past weeks to test an idea against what really happened.
- **Monolith** — one single program (vs. many networked services).

---

*This document describes the v1 design. It will be kept in sync as we build each
phase. If reality and this doc ever disagree, the doc is wrong — tell me and I'll
fix it.*
