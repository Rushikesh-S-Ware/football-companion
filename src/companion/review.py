"""`python -m companion.review` — score Leo's predictions and draft match notes.

After a matchday, this scores every prediction whose match has now finished (right or
wrong), then drafts a match-note file for each — pre-filled with the result and how
Leo's call compared — leaving the "what I saw" parts blank for Rushikesh to fill in.

It does NOT auto-edit opinions.md. Opinions change *deliberately, with a reason* — so
review surfaces the evidence and you (or Leo, in chat) update the takes thoughtfully,
rather than a script rewriting beliefs on its own.
"""

from __future__ import annotations

import re
import sys
import unicodedata

from .predictions import accuracy_stats, score_predictions
from .memory import write_memory

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _slug(text: str) -> str:
    # Strip accents first ("Atlético" -> "atletico") so filenames stay clean ASCII.
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _draft_match_note(scored: dict) -> str:
    """A match-note pre-filled with the facts, leaving human sections blank."""
    verdict = "✅ Right" if scored["correct"] else "❌ Wrong"
    return f"""# {scored['date']} · {scored['match']}
**Result:** {scored['scoreline']} ({scored['actual']})

## The numbers
- (add possession / shots / xG if you have them)

## Story of the match
_(a few sentences on how it went)_

## What I saw (my own eyes)
- _(your observations — the stuff stats miss)_

## Prediction vs reality
- Leo predicted: **{scored['predicted']}** → Actual: **{scored['actual']}** ({scored['scoreline']}) → {verdict}
- What surprised Leo: _(fill in)_

## Did it change my mind?
- _(any opinion that should shift, and why → then update opinions.md)_
"""


def main() -> None:
    print("Scoring Leo's predictions against the results...\n")
    scored = score_predictions()

    if not scored:
        print("No predictions to score yet — either none are logged, or their matches")
        print("haven't been played (and ingested) yet.")
    else:
        for s in scored:
            mark = "✅" if s["correct"] else "❌"
            print(f"  {mark} {s['match']}: predicted {s['predicted']}, actual {s['actual']} ({s['scoreline']})")
            # Draft a match note for Rushikesh to annotate.
            slug = f"{s['date']}_{_slug(s['match'])}"
            path = write_memory("match_note", _draft_match_note(s), slug=slug)
            print(f"     ↳ drafted match note: {path}")

    # Show the running accuracy.
    stats = accuracy_stats()
    print("\n--- Accuracy so far ---")
    if stats["scored"] == 0:
        print("  Nothing scored yet.")
    else:
        pct = 100 * stats["correct"] / stats["scored"]
        print(f"  {stats['correct']}/{stats['scored']} correct ({pct:.0f}%)")
    if stats["pending"]:
        print(f"  ({stats['pending']} prediction(s) still waiting on a result.)")

    if scored:
        print("\nMatch notes drafted in memory/match_notes/ — add your own observations,")
        print("and update memory/opinions.md if any take shifted (with the reason).")


if __name__ == "__main__":
    main()
