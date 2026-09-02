"""Leo — web chat.  Run with:  streamlit run src/companion/webapp.py

Talk to Leo in your browser. It's the SAME Leo as the terminal chat — same brain
(memory + tools + Gemini), so he pulls real data, holds opinions, and remembers what
you tell him. The sidebar shows his live accuracy and current opinions.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from companion import agent
from companion.memory import write_memory
from companion.predictions import accuracy_stats

OPINIONS = Path(__file__).resolve().parents[2] / "memory" / "opinions.md"

st.set_page_config(page_title="Chat with Leo", page_icon="⚽", layout="centered")

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
        with st.spinner("Leo's thinking…"):
            try:
                reply = st.session_state.chat.send_message(prompt).text
            except Exception as exc:  # noqa: BLE001 — keep the page alive on a hiccup
                reply = (
                    "⚠️ Hit a snag — probably the free-tier rate limit. "
                    f"Wait ~30s and try again.\n\n`{exc}`"
                )
        st.markdown(reply)
    st.session_state.history.append(("leo", reply))

# ---- Save the chat to memory ------------------------------------------------
if st.session_state.get("history"):
    if st.button("💾 Save this chat to Leo's memory"):
        try:
            note = st.session_state.chat.send_message(
                "Jot 2-3 bullets of what we discussed for your memory. No preamble."
            ).text.strip()
        except Exception:  # noqa: BLE001
            note = "\n".join(f"- {who}: {text}" for who, text in st.session_state.history[-6:])
        write_memory("discussion", note)
        st.success("Saved to memory/discussions.md ✅ — Leo will remember this next time.")
