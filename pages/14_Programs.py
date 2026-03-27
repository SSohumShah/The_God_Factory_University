"""
Programs & Curriculum — browse degree programs, enroll, track progress.
"""

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_all_courses, credits_earned, compute_gpa, tx, get_academic_progress_summary
from core import db_programs
from ui.theme import inject_theme, gf_header, section_divider, stat_card, help_button

inject_theme()
gf_header("Programs & Curriculum", "Degree programs and academic pathways.")
help_button("programs-overview")

# ─── Current Academic Status ──────────────────────────────────────────────────
section_divider("Your Academic Status")

gpa, graded_count = compute_gpa()
creds = credits_earned()
academic_summary = get_academic_progress_summary()

c1, c2, c3 = st.columns(3)
with c1:
    stat_card("GPA", f"{gpa:.2f}", colour="#ffd700")
with c2:
    stat_card("Verified Credits", str(creds), colour="#40dc80")
with c3:
    stat_card("Verified Courses", str(academic_summary["completed_courses"]), colour="#00d4ff")

st.caption("Program progress below uses verified credits only. Lecture completion and activity do not count until the course audit is fully satisfied.")

# ─── Available Programs ───────────────────────────────────────────────────────
section_divider("Available Programs")

programs = db_programs.get_all_programs(tx)
enrollments = db_programs.get_enrollments(tx)
enrolled_ids = {e["program_id"] for e in enrollments}

if not programs:
    st.info("No programs available yet. Programs are seeded on startup.")
else:
    for prog in programs:
        with st.expander(f"{'[C]' if prog['level'] == 'Certificate' else '[D]'} {prog['name']} --- {prog['level']} ({prog['total_credits']} credits)"):
            st.markdown(f"**School:** {prog.get('school', 'N/A')}")
            st.markdown(f"**Description:** {prog.get('description', '')}")
            st.markdown(f"**Required Credits:** {prog['total_credits']}")

            # Progress bar
            progress = min(creds / prog["total_credits"], 1.0) if prog["total_credits"] > 0 else 0
            st.progress(progress, text=f"{creds}/{prog['total_credits']} verified credits ({progress*100:.0f}%)")

            if prog["id"] in enrolled_ids:
                st.success("[OK] Enrolled")
            else:
                if st.button(f"Enroll in {prog['name']}", key=f"enroll_{prog['id']}"):
                    db_programs.enroll(prog["id"], tx)
                    st.success("Enrolled successfully!")
                    st.rerun()

# ─── Your Enrollments ────────────────────────────────────────────────────────
section_divider("Your Enrollments")

if enrollments:
    for e in enrollments:
        status_icon = "[OK]" if e["status"] == "completed" else "[..]"
        st.markdown(f"- {status_icon} **{e['program_name']}** ({e['program_level']}) — Status: {e['status']}")
else:
    st.caption("Not enrolled in any programs yet. Browse and enroll above!")
