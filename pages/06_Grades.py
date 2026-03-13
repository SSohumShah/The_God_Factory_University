"""
Grades & Transcript — GPA, assignments, degree eligibility, transcript download.
"""

import csv
import io
import json
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_all_courses, get_assignments, compute_gpa, credits_earned,
    eligible_degrees, get_setting, score_to_grade,
    get_enrollment_date, time_to_degree_days, get_terms, get_assignments_by_term,
)
from ui.theme import (
    inject_theme, arcane_header, rune_divider, render_gpa_display,
    degree_display, deadline_pill, help_button,
)

inject_theme()
arcane_header("Grades & Transcript", "Your academic record in the arcane order.")
help_button("gpa-calculation")

student_name = get_setting("student_name", "Scholar")
rune_divider(f"Student: {student_name}")

# ─── GPA + Credit summary ──────────────────────────────────────────────────────
gpa, _ = compute_gpa()
credits = credits_earned()
eligible = eligible_degrees(gpa, credits)
deadlines_on = get_setting("deadlines_enabled", "0") == "1"

g1, g2, g3 = st.columns(3)
with g1:
    render_gpa_display(gpa)
with g2:
    from ui.theme import stat_card
    stat_card("Credits Earned", str(credits), colour="#ffd700")
with g3:
    stat_card("Eligible Degrees", ", ".join(eligible) if eligible else "None yet", colour="#40dc80")

# Enrollment & Time-to-degree
g4, g5 = st.columns(2)
with g4:
    stat_card("Enrolled", get_enrollment_date(), colour="#b8b8d0")
with g5:
    stat_card("Days Studied", str(time_to_degree_days()), colour="#b8b8d0")

# Term grouping (if any terms exist)
terms = get_terms()
if terms:
    rune_divider("Assignments by Term")
    for term in terms:
        ta = get_assignments_by_term(term["id"])
        if not ta:
            continue
        with st.expander(f"Term: {term['title']}  ({len(ta)} assignments)"):
            for a in ta:
                sc = a.get("score") or 0.0
                mx = a.get("max_score") or 100.0
                pct = (sc / mx * 100) if mx else 0.0
                grade, _ = score_to_grade(pct)
                status = "Submitted" if a.get("submitted_at") else "Pending"
                lp = a.get("late_penalty", 0)
                lp_str = f" (late: -{lp:.0f}%)" if lp else ""
                st.markdown(f"- **{a['title']}** — {grade} ({pct:.0f}%) [{status}]{lp_str}")

    stat_card("Days Studied", str(time_to_degree_days()), colour="#b8b8d0")

if eligible:
    degree_display(eligible)

rune_divider("Assignments by Course")

courses = get_all_courses()
if not courses:
    st.info("No courses in the library yet.")
    st.stop()

for course in courses:
    assignments = get_assignments(course["id"])
    if not assignments:
        continue
    with st.expander(f"{course['id']} — {course['title']}  ({len(assignments)} assignments)"):
        rows = []
        for a in assignments:
            score = a.get("score") or 0.0
            max_s = a.get("max_score") or 100.0
            pct = (score / max_s * 100) if max_s else 0.0
            grade, gpa_pts = score_to_grade(pct)
            submitted = bool(a.get("submitted_at"))
            due = a.get("due_at")
            now = time.time()

            status_str = "Graded" if submitted else ("Past due" if (deadlines_on and due and now > due) else "Open")
            rows.append({
                "Title": a["title"],
                "Type": a["type"],
                "Score": f"{score}/{max_s}" if submitted else "—",
                "Grade": grade if submitted else "—",
                "GPA pts": f"{gpa_pts:.1f}" if submitted else "—",
                "Status": status_str,
            })

        if rows:
            st.table(rows)

        # Deadline pills for open assignments
        if deadlines_on:
            open_asns = [a for a in assignments if not a.get("submitted_at") and a.get("due_at")]
            for a in open_asns:
                remaining = a["due_at"] - time.time()
                st.markdown(
                    f"<span style='font-family:monospace;'>{a['title']}  </span>"
                    + deadline_pill(remaining),
                    unsafe_allow_html=True,
                )

rune_divider("Download Transcript")
help_button("transcript-download")

def build_transcript_csv():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Student", student_name])
    writer.writerow(["GPA", f"{gpa:.2f}"])
    writer.writerow(["Credits Earned", credits])
    writer.writerow(["Eligible Degrees", ", ".join(eligible)])
    writer.writerow([])
    writer.writerow(["Course", "Module", "Lecture", "Assignment", "Type", "Score", "Max", "Grade"])

    for course in courses:
        assignments = get_assignments(course["id"])
        for a in assignments:
            score = a.get("score") or 0.0
            max_s = a.get("max_score") or 100.0
            pct = (score / max_s * 100) if max_s else 0.0
            grade, _ = score_to_grade(pct)
            writer.writerow([
                course["title"],
                "",
                "",
                a["title"],
                a["type"],
                score,
                max_s,
                grade if a.get("submitted_at") else "—",
            ])
    return buf.getvalue()

dl1, dl2 = st.columns(2)
with dl1:
    transcript_csv = build_transcript_csv()
    st.download_button(
        "Download Transcript (CSV)",
        transcript_csv,
        file_name=f"transcript_{student_name.replace(' ','_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with dl2:
    transcript_json = {
        "student": student_name,
        "gpa": gpa,
        "credits": credits,
        "eligible_degrees": eligible,
        "courses": [
            {
                "course_id": c["id"],
                "title": c["title"],
                "assignments": get_assignments(c["id"]),
            }
            for c in courses
        ],
    }
    st.download_button(
        "Download Transcript (JSON)",
        json.dumps(transcript_json, indent=2),
        file_name=f"transcript_{student_name.replace(' ','_')}.json",
        mime="application/json",
        use_container_width=True,
    )

rune_divider("Degree Progress")
help_button("degree-eligibility")

DEGREE_TRACKS = {
    "Certificate":  {"min_credits": 15,  "min_gpa": 2.0, "colour": "#40dc80"},
    "Associate":    {"min_credits": 60,  "min_gpa": 2.0, "colour": "#00d4ff"},
    "Bachelor":     {"min_credits": 120, "min_gpa": 2.0, "colour": "#8080ff"},
    "Master":       {"min_credits": 150, "min_gpa": 3.0, "colour": "#ffd700"},
    "Doctorate":    {"min_credits": 180, "min_gpa": 3.5, "colour": "#e04040"},
}

for degree, info in DEGREE_TRACKS.items():
    credit_pct = min(credits / info["min_credits"], 1.0)
    gpa_ok = gpa >= info["min_gpa"]
    unlocked = degree in eligible
    colour = info["colour"] if unlocked else "#303050"

    bar_fill = int(credit_pct * 30)
    bar_empty = 30 - bar_fill
    bar = "█" * bar_fill + "░" * bar_empty

    gpa_marker = "[GPA OK]" if gpa_ok else f"[GPA: need {info['min_gpa']:.1f}]"
    status_marker = "[ELIGIBLE]" if unlocked else "[LOCKED]"

    st.markdown(
        f"<div style='font-family:monospace;margin:4px 0;'>"
        f"<span style='color:{colour};font-weight:bold;'>{degree:<12}</span>  "
        f"<span style='color:#404060;'>[{bar}]</span>  "
        f"<span style='color:#a0a0c0;font-size:0.85rem;'>"
        f"{credits}/{info['min_credits']} cr  {gpa_marker}  "
        f"<span style='color:{colour};'>{status_marker}</span>"
        f"</span></div>",
        unsafe_allow_html=True,
    )
