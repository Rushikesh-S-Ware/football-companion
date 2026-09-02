"""Leo the companion — the Gemini agent: system prompt + tools + a chat session.

We pass our Python tool functions straight to the Gemini SDK. With Python callables
as tools, the SDK does *automatic function calling*: when Leo decides to use a tool,
the SDK runs it and feeds the result back — we don't hand-write the tool loop.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .tools import TOOLS

# Free-tier Gemini sometimes returns transient errors: 429 (rate limit), 503
# (model overloaded / high demand), or 500. These usually clear in a few seconds,
# so we retry before surfacing them.
_TRANSIENT = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500", "overloaded", "high demand")

# The model that works on the free tier (see LEARNING_LOG). Kept as one constant so
# switching providers/models later is a one-line change.
MODEL = "gemini-flash-latest"
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.md"


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def make_client() -> genai.Client:
    """Build a Gemini client from the GEMINI_API_KEY in .env."""
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit(
            "No GEMINI_API_KEY found in .env. Add your free key from "
            "https://aistudio.google.com/apikey (see .env.example)."
        )
    return genai.Client(api_key=key)


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=load_system_prompt(),
        tools=TOOLS,
    )


def new_chat(client: genai.Client, history: list | None = None):
    """Start a fresh chat session with Leo (optionally seeded with prior history)."""
    return client.chats.create(model=MODEL, config=_config(), history=history or [])


def send_message(chat, text: str, retries: int = 3, base_delay: float = 3.0):
    """Send a message to Leo, retrying transient free-tier errors (429/503/500).

    Waits 3s, then 6s, then 9s between tries. Non-transient errors (a bad key, a
    real bug) are raised immediately so they aren't masked.
    """
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return chat.send_message(text)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            transient = any(token in str(exc) for token in _TRANSIENT)
            if transient and attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
                continue
            raise
    raise last_error  # pragma: no cover
