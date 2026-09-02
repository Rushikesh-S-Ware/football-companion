"""`python -m companion.stats` — Leo's prediction accuracy so far.

The honest number, good or bad — overall and by competition. This is the proof that
the learning loop is real: a track record that grows across the season.
"""

from __future__ import annotations

import sys

from .predictions import accuracy_stats

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

COMP_NAMES = {"PD": "La Liga", "CL": "Champions League"}


def main() -> None:
    stats = accuracy_stats()

    print("=" * 40)
    print("  Leo's prediction accuracy")
    print("=" * 40)

    if stats["scored"] == 0:
        print("\n  No predictions scored yet.")
        if stats["pending"]:
            print(f"  {stats['pending']} logged, waiting on results — run `review` after the matches.")
        print("\n  (This fills up as the season plays out.)")
        return

    pct = 100 * stats["correct"] / stats["scored"]
    print(f"\n  Overall: {stats['correct']}/{stats['scored']} correct  ({pct:.0f}%)\n")

    if stats["by_competition"]:
        print("  By competition:")
        for code, n, ok in stats["by_competition"]:
            name = COMP_NAMES.get(code, code)
            p = 100 * ok / n if n else 0
            print(f"    {name:<18} {ok}/{n}  ({p:.0f}%)")

    if stats["pending"]:
        print(f"\n  {stats['pending']} prediction(s) still waiting on a result.")


if __name__ == "__main__":
    main()
