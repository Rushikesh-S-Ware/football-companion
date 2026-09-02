"""Leo — web chat.  Run locally with:  streamlit run src/companion/webapp.py

Talk to Leo in your browser. It's the SAME Leo as the terminal chat — same brain
(memory + tools + Gemini), so he pulls real data, holds opinions, and remembers what
you tell him. The sidebar shows his live accuracy and current opinions.

This file is also the entry point for a Streamlit Cloud deploy: it bootstraps the
import path, reads keys from Streamlit secrets, and pulls data on a fresh host.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the `companion` package importable whether it's pip-installed (local dev) or
# not (a cloud host that only ran `pip install -r requirements.txt`). webapp.py lives
# at src/companion/webapp.py, so parents[1] is `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

st.set_page_config(page_title="Chat with Leo", page_icon="⚽", layout="centered")

# On a cloud host there is no .env — bridge Streamlit secrets into environment
# variables so the existing os.getenv-based code (agent, ingest) works unchanged.
# Locally there's no secrets file, so this quietly no-ops and .env is used instead.
try:
    for _key in ("GEMINI_API_KEY", "FOOTBALL_DATA_API_TOKEN", "API_FOOTBALL_KEY"):
        if _key in st.secrets and not os.getenv(_key):
            os.environ[_key] = str(st.secrets[_key])
except Exception:  # noqa: BLE001 — no secrets file (running locally with .env)
    pass

from companion import agent
from companion.db import connect, init_schema
from companion.memory import write_memory
from companion.predictions import accuracy_stats

OPINIONS = Path(__file__).resolve().parents[2] / "memory" / "opinions.md"


@st.cache_resource(show_spinner="Loading the latest football data…")
def _ensure_data() -> bool:
    """A fresh host starts with an empty database — pull data once on first load."""
    con = connect()
    init_schema(con)
    empty = con.execute("SELECT count(*) FROM matches").fetchone()[0] == 0
    con.close()
    if empty and os.getenv("FOOTBALL_DATA_API_TOKEN"):
        from companion.ingest import run_ingest

        run_ingest(light=True)  # La Liga only — fast; run the full `ingest` for UCL + news
    return True


_ensure_data()

# ---- Sidebar: Leo's live stats + opinions -----------------------------------
with st.sidebar:
    st.header("⚽ Leo")
    st.caption("Culé at heart, honest in the head.")
    stats = accuracy_stats()
    if stats["scored"]:
        pct = 100 * stats["correct"] / stats["scored"]
        st.metric("Prediction accuracy", f"{pct:.0f}%", f"{stats['correct']}/{stats['scored']} correct")
    else:
        st.caption("No predictions scored yet.")
    with st.expander("💭 His current opinions"):
        st.markdown(OPINIONS.read_text(encoding="utf-8") if OPINIONS.exists() else "—")
    st.caption("Free tier — if he rate-limits, wait ~30s and retry.")

st.title("💬 Chat with Leo")

# ---- Start Leo once per browser session -------------------------------------
if "chat" not in st.session_state:
    try:
        st.session_state.client = agent.make_client()
    except SystemExit as exc:
        st.error(str(exc))
        st.stop()
    st.session_state.chat = agent.new_chat(st.session_state.client)
    st.session_state.history = []  # list of (speaker, text)

# ---- Render the transcript so far -------------------------------------------
for speaker, text in st.session_state.history:
    avatar = "🧑" if speaker == "you" else "⚽"
    with st.chat_message("user" if speaker == "you" else "assistant", avatar=avatar):
        st.markdown(text)

# ---- Input box --------------------------------------------------------------
if prompt := st.chat_input("Ask Leo about a match, a player, a tactic…"):
    st.session_state.history.append(("you", prompt))
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="⚽"):
        with st.spinner("Leo's thinking… (auto-retries if Gemini is busy)"):
            try:
                reply = agent.send_message(st.session_state.chat, prompt).text
            except Exception as exc:  # noqa: BLE001 — keep the page alive on a hiccup
                reply = (
                    "⚠️ Gemini's free tier is busy or rate-limited right now "
                    "(it gets deprioritized when demand spikes). Give it a minute and "
                    f"resend.\n\n`{exc}`"
                )
        st.markdown(reply)
    st.session_state.history.append(("leo", reply))

# ---- Save the chat to memory ------------------------------------------------
if st.session_state.get("history"):
    if st.button("💾 Save this chat to Leo's memory"):
        try:
            note = agent.send_message(
                st.session_state.chat,
                "Jot 2-3 bullets of what we discussed for your memory. No preamble.",
            ).text.strip()
        except Exception:  # noqa: BLE001
            note = "\n".join(f"- {who}: {text}" for who, text in st.session_state.history[-6:])
        write_memory("discussion", note)
        st.success("Saved to memory/discussions.md ✅ — Leo will remember this next time.")
