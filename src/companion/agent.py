"""Leo the companion — the agent brain (Groq / Llama, OpenAI-style tool calling).

Groq runs open Llama models on very fast hardware, so replies come back quickly. Unlike
Gemini's *automatic* function calling, here we drive the tool loop ourselves: the model
returns `tool_calls`, we run the matching Python function, feed the result back, and
repeat until it answers. The model is one constant (`MODEL`) so swapping provider/model
stays a small change.
"""

from __future__ import annotations

import inspect
import json
import os
import time
from pathlib import Path
from typing import get_type_hints

from dotenv import load_dotenv
from groq import Groq

from .tools import TOOLS

# A fast, tool-capable model on Groq's free tier. If it's not available on the
# account, we auto-pick the best available one (see resolve_model) — Groq changes
# its model lineup, and bigger models aren't always on the free tier.
MODEL = "llama-3.1-8b-instant"
# Tried in order; first one the account actually has wins. All support tool calls.
_PREFERRED_MODELS = [
    MODEL,
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3-32b",
    "llama3-8b-8192",
]
_resolved_model: str | None = None

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.md"

# Transient errors worth a retry (rate limit / overload / server blip).
_TRANSIENT = ("rate limit", "429", "503", "overload", "unavailable", "500", "try again")
_MAX_TOOL_STEPS = 6  # safety cap on the tool-call loop

# name -> the Python function to run when the model calls that tool.
DISPATCH = {func.__name__: func for func in TOOLS}


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def make_client() -> Groq:
    """Build a Groq client from GROQ_API_KEY in .env."""
    load_dotenv()
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise SystemExit(
            "No GROQ_API_KEY found in .env. Get a free key at "
            "https://console.groq.com/keys (see .env.example)."
        )
    return Groq(api_key=key)


def _tool_schema(func) -> dict:
    """Build an OpenAI/Groq tool schema from a Python function's signature + docstring.

    We resolve type hints (get_type_hints handles the stringified annotations from
    `from __future__ import annotations`), map int->integer / everything else->string,
    and mark parameters without a default as required.
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    properties, required = {}, []
    for name, param in sig.parameters.items():
        annotation = hints.get(name, str)
        properties[name] = {"type": "integer" if annotation is int else "string"}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    description = " ".join((func.__doc__ or "").split())
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_SCHEMAS = [_tool_schema(func) for func in TOOLS]


def resolve_model(client: Groq) -> str:
    """Pick a model this account actually has access to (cached after the first call).

    Tries the preferred list, then falls back to any chat model the account exposes,
    skipping audio / safety / embedding models. This keeps Leo working even when Groq
    renames or gates models.
    """
    global _resolved_model
    if _resolved_model:
        return _resolved_model
    try:
        available = {m.id for m in client.models.list().data}
    except Exception:  # noqa: BLE001 — can't list; just try the default
        _resolved_model = MODEL
        return _resolved_model
    for name in _PREFERRED_MODELS:
        if name in available:
            _resolved_model = name
            return name
    for model_id in available:  # last resort: any non-audio/guard model
        if not any(x in model_id.lower() for x in ("whisper", "tts", "guard", "embed")):
            _resolved_model = model_id
            return model_id
    _resolved_model = MODEL
    return _resolved_model


def _run_tool(name: str, args: dict) -> str:
    """Execute one tool call and return its result as a string."""
    func = DISPATCH.get(name)
    if func is None:
        return f"(unknown tool: {name})"
    try:
        return str(func(**args))
    except Exception as exc:  # noqa: BLE001 — hand the error back so Leo can recover
        return f"(tool error: {exc})"


def _complete(client: Groq, messages: list, use_tools: bool, retries: int = 3, base_delay: float = 2.0):
    """Call Groq once, retrying transient errors (429/503/500) with backoff."""
    model = resolve_model(client)
    for attempt in range(retries):
        try:
            kwargs: dict = {"model": model, "messages": messages, "temperature": 0.7}
            if use_tools:
                kwargs["tools"] = TOOL_SCHEMAS
                kwargs["tool_choice"] = "auto"
            return client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            transient = any(token in str(exc).lower() for token in _TRANSIENT)
            if transient and attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
                continue
            raise


class LeoChat:
    """A running conversation with Leo — holds the message history and drives the tools."""

    def __init__(self, client: Groq, history: list | None = None):
        self.client = client
        self.messages: list = [{"role": "system", "content": load_system_prompt()}]
        if history:
            self.messages.extend(history)

    def send(self, text: str) -> str:
        """Send a user message; run any tool calls; return Leo's final reply text."""
        self.messages.append({"role": "user", "content": text})
        for _ in range(_MAX_TOOL_STEPS):
            message = _complete(self.client, self.messages, use_tools=True).choices[0].message
            if message.tool_calls:
                # Record the assistant's tool request, then each tool's result.
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                            }
                            for tc in message.tool_calls
                        ],
                    }
                )
                for tc in message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    self.messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": _run_tool(tc.function.name, args)}
                    )
                continue  # loop again so Leo can use the results
            self.messages.append({"role": "assistant", "content": message.content or ""})
            return message.content or ""
        return "(I got a bit tangled using my tools — try asking that a different way.)"


def new_chat(client: Groq, history: list | None = None) -> LeoChat:
    """Start a fresh conversation with Leo (optionally seeded with prior history)."""
    return LeoChat(client, history=history)


def send_message(chat: LeoChat, text: str) -> str:
    """Send a message to Leo and get his reply as a string."""
    return chat.send(text)


def generate(client: Groq, prompt: str) -> str:
    """One-shot generation in Leo's voice, no tools (used by the briefing command)."""
    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": prompt},
    ]
    return _complete(client, messages, use_tools=False).choices[0].message.content or ""
