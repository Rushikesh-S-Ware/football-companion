"""Leo's dashboard — run with:  streamlit run src/companion/dashboard.py

One page that shows what the season looks like through Leo's eyes: his prediction
accuracy, his living opinions, and the archive of briefings he's written. It only
*reads* — everything here is produced by the ingest / briefing / review commands.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from companion.db import connect, init_schema
from companion.predictions import accuracy_stats

BASE = Path(__file__).resolve().parents[2]
MEMORY = BASE / "memory"
BRIEFINGS = BASE / "briefings"

st.set_page_config(page_title="Leo — Football Companion", page_icon="⚽", layout="wide")

st.title("⚽ Leo — Football Companion")
st.caption(
    "A Culé analyst who pulls real La Liga / Champions League data, holds opinions, "
    "and scores his own predictions across the season."
)

# ----------------------------------------------------------------------------
# Prediction accuracy — the honest number that proves the learning loop is real.
# ----------------------------------------------------------------------------
st.header("📊 Prediction accuracy")

stats = accuracy_stats()
scored, correct = stats["scored"], stats["correct"]
pct = (100 * correct / scored) if scored else 0

c1, c2, c3 = st.columns(3)
c1.metric("Predictions scored", scored)
c2.metric("Correct", correct)
c3.metric("Accuracy", f"{pct:.0f}%" if scored else "—")

if stats["pending"]:
    st.info(f"{stats['pending']} prediction(s) still waiting on a result.")

con = connect()
init_schema(con)
df = con.execute(
    """SELECT created_at, match_label, competition_code, predicted_result,
              confidence, correct
       FROM predictions ORDER BY created_at"""
).df()
con.close()

if not df.empty:
    played = df[df["correct"].notna()].reset_index(drop=True)
    if not played.empty:
        played["cumulative accuracy %"] = (
            100 * played["correct"].astype(int).cumsum() / (played.index + 1)
        )
        st.line_chart(played.set_index("match_label")["cumulative accuracy %"])
    st.subheader("All predictions")
    st.dataframe(
        df[["match_label", "competition_code", "predicted_result", "confidence", "correct"]],
        use_container_width=True,
    )
else:
    st.write("No predictions logged yet — run a briefing to log one.")

# ----------------------------------------------------------------------------
# Opinions — Leo's living takes (the versioned brain).
# ----------------------------------------------------------------------------
st.header("💭 Leo's opinions")
opinions = MEMORY / "opinions.md"
st.markdown(opinions.read_text(encoding="utf-8") if opinions.exists() else "_No opinions yet._")

# ----------------------------------------------------------------------------
# Briefing archive — every pre-match briefing Leo has written.
# ----------------------------------------------------------------------------
st.header("📝 Briefing archive")
briefs = sorted((b for b in BRIEFINGS.glob("*.md")), reverse=True)
if not briefs:
    st.write("No briefings yet — run `python -m companion.briefing --next-barca`.")
for b in briefs:
    with st.expander(b.stem.replace("_", "  ·  ")):
        st.markdown(b.read_text(encoding="utf-8"))
