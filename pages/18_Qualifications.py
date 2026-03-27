"""
Qualifications Dashboard — track real-world benchmark equivalencies and qualification progress.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_all_benchmarks, check_qualifications, get_qualifications,
    get_qualification_roadmap, compute_gpa, credits_earned,
    course_credit_hours, get_competency_profile, BLOOMS_LEVELS,
    get_benchmark_comparison, get_academic_progress_summary,
)
from core.ui_mode import require_ui_mode
from ui.theme import inject_theme, gf_header, section_divider, stat_card, help_button

inject_theme()
require_ui_mode(("operator",), "Qualifications")
gf_header("Qualifications", "Evidence-based benchmark tracking and study planning.")
help_button("qualifications-dashboard")
st.warning("Benchmark status on this page uses verified course evidence and mastery gates, but it is still internal planning guidance rather than an official external credential award.")

# ─── Overview ──────────────────────────────────────────────────────────────────
gpa, _ = compute_gpa()
credits = credits_earned()
academic_summary = get_academic_progress_summary()

o1, o2, o3 = st.columns(3)
with o1:
    stat_card("GPA", f"{gpa:.2f}", colour="#ffd700")
with o2:
    stat_card("Verified Credits", f"{credits:.2f}", colour="#00d4ff")
with o3:
    benchmarks = get_all_benchmarks()
    stat_card("Tracked Benchmarks", str(len(benchmarks)), colour="#ff8c00")

st.caption(
    f"Activity credits: {academic_summary['activity_credits']:.2f} | "
    f"Verified courses: {academic_summary['completed_courses']} | "
    f"These benchmark percentages are estimates, not awarded qualifications."
)

section_divider("Qualification Progress")

# Recompute qualifications
if st.button("Refresh Qualification Status"):
    with st.spinner("Evaluating benchmarks..."):
        check_qualifications()
    st.rerun()

qualifications = get_qualifications()
if not qualifications:
    st.info("No qualifications tracked yet. Benchmarks will appear as you enroll in courses.")
    st.stop()

for q in qualifications:
    status = q.get("status", "locked")
    status_mark = {"earned": "[OK]", "in_progress": "[..]", "locked": "[--]"}.get(status, "[??]")
    pct = q.get("progress_pct", 0)

    with st.expander(f"{status_mark}  {q['name']}  ({pct:.0f}%)", expanded=(status == "in_progress")):
        st.markdown(f"**{q.get('description', '')}**")
        st.caption(f"School: {q.get('school_ref', 'N/A')} | Category: {q.get('category', 'academic')}")

        # Progress bar
        st.progress(min(pct / 100, 1.0))

        # Requirements
        c1, c2, c3 = st.columns(3)
        with c1:
            stat_card("Min GPA", f"{q.get('min_gpa', 0):.1f}", colour="#ffd700")
        with c2:
            stat_card("Min Hours", f"{q.get('min_hours', 0):.0f}", colour="#00d4ff")
        with c3:
            req_courses = q.get("required_courses", [])
            stat_card("Required Courses", str(len(req_courses)), colour="#ff8c00")

        # Benchmark Comparison & Gap Analysis
        if q.get("id"):
            comp = get_benchmark_comparison(q["id"])
            if comp and "error" not in comp:
                section_divider("Benchmark Comparison (Estimated)")
                bc1, bc2, bc3 = st.columns(3)
                with bc1:
                    stat_card("Verified Course Coverage", f"{comp['coverage_pct']:.0f}%", colour="#40dc80")
                with bc2:
                    stat_card("Hours Progress", f"{comp['hours_logged']:.0f}/{comp['hours_required']:.0f}",
                              colour="#00d4ff")
                with bc3:
                    rigor = comp["rigor_pct"]
                    r_colour = "#40dc80" if rigor >= 80 else "#ffd700" if rigor >= 50 else "#e04040"
                    stat_card("Rigor Rating", f"{rigor:.0f}%", colour=r_colour)

                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    stat_card("Mastery", f"{comp['mastery_pct']:.0f}%", colour="#ffd700")
                with mc2:
                    stat_card("Assessment Evidence", f"{comp['assessment_pct']:.0f}%", colour="#ff8c00")
                with mc3:
                    stat_card("Verified Courses", f"{comp['covered_topics']}/{comp['total_topics']}", colour="#40dc80")

                st.markdown(
                    f"Your verified coursework covers **{comp['covered_topics']}** of "
                    f"**{comp['total_topics']}** required benchmark courses from {comp.get('school', 'target')} mappings."
                )

                # Gap Analysis
                gap = comp.get("gap_topics", [])
                if gap:
                    st.markdown("**Remaining mapped courses to verify for this benchmark:**")
                    for t in gap:
                        st.markdown(f"- {t}")

        # Roadmap
        if status != "earned" and q.get("id"):
            roadmap = get_qualification_roadmap(q["id"])
            if roadmap and "error" not in roadmap:
                completed = roadmap.get("completed", [])
                remaining = roadmap.get("remaining", [])
                hours_logged = roadmap.get("hours_logged", 0)

                if completed:
                    st.markdown("**Courses with matching progress evidence:** " + ", ".join(f"`{c}`" for c in completed))
                if remaining:
                    st.markdown("**Courses still recommended:** " + ", ".join(f"`{c}`" for c in remaining))

                st.caption(
                    f"Hours: {hours_logged:.1f} / {roadmap.get('hours_needed', 0):.0f} | "
                    f"GPA requirement: {roadmap.get('min_gpa', 0):.1f}")
