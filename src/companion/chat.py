"""`python -m companion.chat` — talk to Leo in the terminal.

Leo reads/writes his memory and pulls real data through tools. To keep context (and
free-tier cost) under control, once the conversation gets long we summarize the older
turns and continue from that summary. At the end we save a short note to discussions.md
so Leo remembers this chat next time.
"""

from __future__ import annotations

import sys

from . import agent
from .memory import write_memory

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BANNER = (
    "⚽ Leo — your Barça football companion. Real data, real opinions.\n"
    "   Type 'exit' when you're done.\n"
)

# After this many exchanges, compress older turns so context stays small.
COMPACT_EVERY = 12


def _compact(client, chat):
    """Summarize the conversation so far and restart with that summary as context."""
    try:
        summary = agent.send_message(
            chat,
            "Summarize our conversation so far in a few sentences so we can continue "
            "with less context. Just the summary, no preamble.",
        ).strip()
    except Exception:
        return chat  # if it fails, just keep the existing chat
    seed = [
        {"role": "user", "content": f"Summary of our chat so far: {summary}"},
        {"role": "assistant", "content": "Got it — I remember where we're at."},
    ]
    return agent.new_chat(client, history=seed)


def _save_discussion(chat) -> None:
    """Write a short end-of-session note to discussions.md."""
    try:
        note = agent.send_message(
            chat,
            "Before we go, jot 2-3 short bullet points of what we discussed today for "
            "your memory — anything I told you, or any take that shifted. No preamble.",
        ).strip()
    except Exception:
        note = "Chatted about football (summary unavailable)."
    write_memory("discussion", note)
    print("\n(Saved a note about our chat to memory.)")


def main() -> None:
    client = agent.make_client()
    chat = agent.new_chat(client)
    print(BANNER)

    exchanges = 0
    try:
        while True:
            try:
                user = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                continue
            if user.lower() in ("exit", "quit", "bye"):
                break
            try:
                reply = agent.send_message(chat, user)
                print(f"\nLeo: {reply}\n")
                exchanges += 1
                if exchanges % COMPACT_EVERY == 0:
                    chat = _compact(client, chat)
            except Exception as exc:  # noqa: BLE001 — keep the chat alive on a hiccup
                print(f"\n[Leo hit a snag: {exc}]\n")
    finally:
        if exchanges:
            _save_discussion(chat)
        print("Força Barça. 👋")


if __name__ == "__main__":
    main()
