"""
Statistics & Analytics — activity dashboard, study hours, grade trends.
"""

import sys
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_xp, count_completed, get_all_courses, get_assignments,
    compute_gpa, credits_earned, tx, get_academic_progress_summary,
)
from core import db_activity
from ui.theme import inject_theme, gf_header, section_divider, stat_card, help_button

inject_theme()
gf_header("Statistics", "Your academic analytics dashboard.")
help_button("statistics-dashboard")

# ─── Summary Cards ────────────────────────────────────────────────────────────
section_divider("Overview")

summary = db_activity.get_activity_summary(tx)
academic_summary = get_academic_progress_summary()
gpa, graded = compute_gpa()
completed = count_completed()
courses = len(get_all_courses())
assignments = get_assignments()
submitted = [a for a in assignments if a.get("submitted_at")]

c1, c2, c3, c4 = st.columns(4)
with c1:
    stat_card("Study Hours", f"{summary['study_hours']:.1f}", colour="#ffd700")
with c2:
    stat_card("Lectures Done", str(completed), colour="#40dc80")
with c3:
    stat_card("Assignments", str(len(submitted)), colour="#00d4ff")
with c4:
    stat_card("GPA", f"{gpa:.2f}", colour="#c060ff")

c5, c6, c7, c8 = st.columns(4)
with c5:
    stat_card("Courses", str(courses), colour="#ff8040")
with c6:
    stat_card("Verified Credits", str(credits_earned()), colour="#ffd700")
with c7:
    stat_card("Total XP", str(get_xp()), colour="#40dc80")
with c8:
    stat_card("Activities", str(summary["total_events"]), colour="#00d4ff")

st.caption(
    f"Activity credits: {academic_summary['activity_credits']:.2f} | "
    f"Verified courses: {academic_summary['completed_courses']} | "
    f"Verified assessments: {academic_summary['verified_assessments']}"
)

# ─── Daily Activity Chart ────────────────────────────────────────────────────
section_divider("Daily Activity (Last 30 Days)")

daily = db_activity.get_daily_counts(tx, days=30)
if daily:
    import pandas as pd
    df = pd.DataFrame(daily)
    df.columns = ["Day", "Activities"]
    st.bar_chart(df.set_index("Day"))
else:
    st.caption("No activity data yet. Start learning to see your stats!")

# ─── Activity Breakdown ──────────────────────────────────────────────────────
section_divider("Activity Breakdown")

by_type = summary.get("by_type", {})
if by_type:
    for event_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        label = event_type.replace("_", " ").title()
        st.markdown(f"- **{label}**: {count} events")
else:
    st.caption("No activities recorded yet.")

# ─── Grade Distribution ──────────────────────────────────────────────────────
section_divider("Grade Distribution")

if submitted:
    scores = [a["score"] for a in submitted if a.get("score") is not None]
    if scores:
        import pandas as pd
        grade_ranges = {"A (90-100)": 0, "B (80-89)": 0, "C (70-79)": 0, "D (60-69)": 0, "F (<60)": 0}
        for s in scores:
            if s >= 90:
                grade_ranges["A (90-100)"] += 1
            elif s >= 80:
                grade_ranges["B (80-89)"] += 1
            elif s >= 70:
                grade_ranges["C (70-79)"] += 1
            elif s >= 60:
                grade_ranges["D (60-69)"] += 1
            else:
                grade_ranges["F (<60)"] += 1
        df = pd.DataFrame(list(grade_ranges.items()), columns=["Grade", "Count"])
        st.bar_chart(df.set_index("Grade"))
    else:
        st.caption("No scored assignments yet.")
else:
    st.caption("Submit assignments to see grade distribution.")
