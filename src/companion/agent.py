"""Leo the companion — the Gemini agent: system prompt + tools + a chat session.

We pass our Python tool functions straight to the Gemini SDK. With Python callables
as tools, the SDK does *automatic function calling*: when Leo decides to use a tool,
the SDK runs it and feeds the result back — we don't hand-write the tool loop.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .tools import TOOLS

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
