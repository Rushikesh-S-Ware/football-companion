"""The memory tools: read and write the companion's markdown "brain".

The brain lives in memory/ as human-readable markdown (committed to git). These two
functions are what the agent uses to remember and record things. They are
**simple on purpose** — filename + keyword search, most-recent-first — per the spec.
No embeddings, no vector database (that's a phase-2 idea only if this proves too weak).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = REPO_ROOT / "memory"


def _markdown_files(memory_dir: Path) -> list[Path]:
    """Every markdown memory file, except the blank template."""
    return [p for p in memory_dir.rglob("*.md") if p.name != "_TEMPLATE.md"]


def _excerpt(text: str, terms: list[str], width: int = 220) -> str:
    """A short snippet of `text`, centred on the first matching term if there is one."""
    if terms:
        lowered = text.lower()
        hits = [lowered.find(t) for t in terms if lowered.find(t) != -1]
        if hits:
            start = max(0, min(hits) - 60)
            return text[start : start + width].strip()
    return text[:width].strip()


def read_memory(query: str = "", memory_dir: Path | str = MEMORY_DIR, limit: int = 5) -> list[dict]:
    """Search the memory files and return the best matches, most recent first.

    Scoring is deliberately simple: count how often the query words appear in each
    file's name + contents. Files with no match are skipped (unless the query is
    empty, in which case we just return the most recently updated files). Ties break
    by most-recently-modified — so fresh memories surface first.
    """
    memory_dir = Path(memory_dir)
    terms = [t.lower() for t in query.split()]
    results: list[dict] = []

    for path in _markdown_files(memory_dir):
        text = path.read_text(encoding="utf-8")
        haystack = f"{path.name}\n{text}".lower()
        score = sum(haystack.count(term) for term in terms)
        if terms and score == 0:
            continue  # a query was given but this file doesn't match
        results.append(
            {
                "source": str(path.relative_to(memory_dir.parent)),
                "updated": dt.datetime.fromtimestamp(path.stat().st_mtime),
                "score": score,
                "excerpt": _excerpt(text, terms),
            }
        )

    # Sort by relevance first, then recency. Both descending (higher/newer first).
    results.sort(key=lambda r: (r["score"], r["updated"]), reverse=True)
    return results[:limit]


def _append(path: Path, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(existing + text, encoding="utf-8")


def write_memory(
    mem_type: str,
    content: str,
    slug: str | None = None,
    memory_dir: Path | str = MEMORY_DIR,
    now: dt.datetime | None = None,
) -> Path:
    """Record something into memory. Returns the file it wrote to.

    mem_type:
      - "discussion" -> append a dated entry to discussions.md
      - "opinion"    -> append text to opinions.md (a new take, or a change note)
      - "match_note" -> write a new file memory/match_notes/<slug>.md (needs `slug`)
    """
    memory_dir = Path(memory_dir)
    now = now or dt.datetime.now()

    if mem_type == "discussion":
        path = memory_dir / "discussions.md"
        _append(path, f"\n## {now:%Y-%m-%d}\n{content.strip()}\n")
        return path

    if mem_type == "opinion":
        path = memory_dir / "opinions.md"
        _append(path, f"\n{content.strip()}\n")
        return path

    if mem_type == "match_note":
        if not slug:
            raise ValueError("match_note needs a slug, e.g. '2026-08-23_barcelona-vs-elche'")
        notes_dir = memory_dir / "match_notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = notes_dir / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        return path

    raise ValueError(f"unknown memory type: {mem_type!r} (use discussion/opinion/match_note)")
