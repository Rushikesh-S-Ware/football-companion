"""Leo the companion — the agent brain (Google Gemini, automatic function calling).

We went back to Gemini after Groq's free-tier model kept *inventing* results instead
of calling tools. Gemini reliably uses the tools and stays grounded — slower, but
honest, which is the whole point of this project.

We pass our Python tool functions straight to the SDK. With Python callables as tools,
Gemini does *automatic function calling*: when Leo decides to use a tool, the SDK runs
it and feeds the result back — we don't hand-write the tool loop. The model is one
constant (`MODEL`) so swapping provider/model stays a small change.
"""

from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .tools import TOOLS

MODEL = "gemini-flash-latest"
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.md"

# Transient errors worth a retry (rate limit / overload / server blip).
_TRANSIENT = ("429", "resource_exhausted", "503", "unavailable", "500", "overload", "try again")


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _runtime_guard() -> str:
    """A blunt, always-on rule appended to the system prompt: use tools, never invent.

    Dates the conversation so 'recent matches' is read correctly, and makes the
    grounding discipline explicit so Leo never fabricates a scoreline or a player.
    """
    today = dt.date.today().isoformat()
    return (
        f"\n\n--- HARD RULES (do not break) ---\n"
        f"Today's date is {today}. You have NO reliable knowledge of match results, "
        "fixtures, standings, form, lineups, or which players are in the squad from your "
        "own training — that information changes constantly and yours would be wrong.\n"
        "• To mention ANY result, scoreline, fixture, table position, form, injury, or "
        "player, you MUST first call the matching tool (get_results, get_fixtures, "
        "get_standings, get_team_form, get_news, get_lineups_and_injuries, read_memory).\n"
        "• If a tool returns nothing (e.g. the season hasn't started yet), say so plainly. "
        "NEVER invent a scoreline, a stat, or a player name to fill the gap — that is the "
        "single worst thing you can do.\n"
        "• If you're not sure, say 'let me check' and call a tool, or admit you don't know."
    )


def make_client() -> genai.Client:
    """Build a Gemini client from GEMINI_API_KEY in .env."""
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit(
            "No GEMINI_API_KEY found in .env. Get a free key at "
            "https://aistudio.google.com/apikey (see .env.example)."
        )
    return genai.Client(api_key=key)


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=load_system_prompt() + _runtime_guard(),
        tools=TOOLS,
    )


def _to_gemini_history(history: list | None) -> list:
    """Convert our simple [{'role','content'}] history into Gemini Content objects."""
    out = []
    for msg in history or []:
        role = "model" if msg.get("role") == "assistant" else "user"
        out.append(types.Content(role=role, parts=[types.Part(text=msg.get("content", ""))]))
    return out


def new_chat(client: genai.Client, history: list | None = None):
    """Start a fresh chat session with Leo (optionally seeded with prior history)."""
    return client.chats.create(model=MODEL, config=_config(), history=_to_gemini_history(history))


def _is_transient(exc: Exception) -> bool:
    return any(token in str(exc).lower() for token in _TRANSIENT)


def send_message(chat, text: str, retries: int = 3, base_delay: float = 3.0) -> str:
    """Send a message to Leo, retrying transient errors, and return his reply as text."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return chat.send_message(text).text or ""
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if _is_transient(exc) and attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
                continue
            raise
    raise last_error  # pragma: no cover


def generate(client: genai.Client, prompt: str, retries: int = 3, base_delay: float = 3.0) -> str:
    """One-shot generation in Leo's voice, no tools (used by the briefing command)."""
    config = types.GenerateContentConfig(system_instruction=load_system_prompt() + _runtime_guard())
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=MODEL, contents=prompt, config=config)
            return resp.text or ""
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if _is_transient(exc) and attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
                continue
            raise
    raise last_error  # pragma: no cover
