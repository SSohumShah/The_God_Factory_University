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
    course_credit_hours, course_completion_pct, hours_to_credits,
    get_competency_profile, BLOOMS_LEVELS, get_assignment_ai_policy,
    time_to_degree_estimate, get_assessment_hours, DEGREE_TRACKS,
    get_academic_progress_summary, get_course_completion_audit,
)
from ui.theme import (
    inject_theme, gf_header, section_divider, render_gpa_display,
    degree_display, deadline_pill, help_button,
)

inject_theme()
gf_header("Grades & Transcript", "Your academic record at The God Factory.")
help_button("gpa-calculation")

student_name = get_setting("student_name", "Scholar")
section_divider(f"Student: {student_name}")

# ─── GPA + Credit summary ──────────────────────────────────────────────────────
gpa, _ = compute_gpa()
credits = credits_earned()
eligible = eligible_degrees(gpa, credits)
deadlines_on = get_setting("deadlines_enabled", "0") == "1"
academic_summary = get_academic_progress_summary()
activity_credits = academic_summary["activity_credits"]

g1, g2, g3 = st.columns(3)
with g1:
    render_gpa_display(gpa)
with g2:
    from ui.theme import stat_card
    stat_card("Verified Credits", f"{credits:.2f}", colour="#ffd700")
with g3:
    stat_card("Eligible Degrees", ", ".join(eligible) if eligible else "None yet", colour="#40dc80")

a1, a2, a3 = st.columns(3)
with a1:
    stat_card("Activity Credits", f"{activity_credits:.2f}", colour="#00d4ff")
with a2:
    stat_card("Verified Courses", str(academic_summary["completed_courses"]), colour="#40dc80")
with a3:
    stat_card("Verified Assessments", str(academic_summary["verified_assessments"]), colour="#ff8c00")

st.caption("Verified credits require full lecture completion, passing graded assessments, and course mastery evidence. Activity credits track progress but do not count as official degree credit.")

# Credit-hours summary
total_hours = sum(course_credit_hours(c["id"]) for c in get_all_courses())
hour_credits = hours_to_credits(total_hours)
assess_hours = sum(get_assessment_hours(c["id"]) for c in get_all_courses())
h1, h2, h3 = st.columns(3)
with h1:
    stat_card("Total Study Hours", f"{total_hours:.1f}", colour="#00d4ff")
with h2:
    stat_card("Assessment Hours", f"{assess_hours:.1f}", colour="#e04040")
with h3:
    stat_card("Hour-Based Credits", f"{hour_credits:.1f}", colour="#ff8c00")

# Enrollment & Time-to-degree
g4, g5 = st.columns(2)
with g4:
    stat_card("Enrolled", get_enrollment_date(), colour="#b8b8d0")
with g5:
    stat_card("Days Studied", str(time_to_degree_days()), colour="#b8b8d0")

# Term grouping (if any terms exist)
terms = get_terms()
if terms:
    section_divider("Assignments by Term")
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
                grading_status = "Submitted" if a.get("score") is not None else "Pending review" if a.get("submitted_at") else "Pending"
                lp = a.get("late_penalty", 0)
                lp_str = f" (late: -{lp:.0f}%)" if lp else ""
                st.markdown(f"- **{a['title']}** — {grade if a.get('score') is not None else 'Ungraded'} ({pct:.0f}% if graded) [{grading_status}]{lp_str}")

    stat_card("Days Studied", str(time_to_degree_days()), colour="#b8b8d0")

if eligible:
    degree_display(eligible)

section_divider("Assignments by Course")

_AI_BADGE = {
    "unrestricted": "<span style='color:#40dc80;' title='AI: Unrestricted'>[OPEN]</span>",
    "assisted": "<span style='color:#ffd700;' title='AI: Assisted'>[AIDED]</span>",
    "supervised": "<span style='color:#ff8c00;' title='AI: Supervised'>[WATCH]</span>",
    "prohibited": "<span style='color:#e04040;' title='AI: Prohibited'>[NONE]</span>",
}

courses = get_all_courses()
if not courses:
    st.info("No courses in the library yet.")
    st.stop()

for course in courses:
    assignments = get_assignments(course["id"])
    cr_hours = course_credit_hours(course["id"])
    comp_pct = course_completion_pct(course["id"])
    course_audit = get_course_completion_audit(course["id"])
    course_credits = course["credits"]
    fractional = round(comp_pct / 100.0 * course_credits, 2) if course_credits else 0

    label = f"{course['id']} -- {course['title']}  ({len(assignments)} asgn"
    if cr_hours > 0:
        label += f", {cr_hours:.1f}h, activity {fractional:.2f}/{course_credits} cr"
    if course_audit["verified_complete"]:
        label += ", verified complete"
    label += ")"
    if not assignments:
        continue
    with st.expander(label):
        st.caption(
            f"Verified completion: {'yes' if course_audit['verified_complete'] else 'not yet'} | "
            f"Official credits: {course_audit['official_credits']:.2f} | "
            f"Activity credits: {course_audit['activity_credits']:.2f} | "
            f"Passed assignments: {course_audit['passed_assignments']}/{course_audit['total_assignments']}"
        )
        rows = []
        for a in assignments:
            score = a.get("score") or 0.0
            max_s = a.get("max_score") or 100.0
            pct = (score / max_s * 100) if max_s else 0.0
            grade, gpa_pts = score_to_grade(pct)
            submitted = bool(a.get("submitted_at"))
            due = a.get("due_at")
            now = time.time()
            policy = get_assignment_ai_policy(a)
            badge = _AI_BADGE.get(policy.get("level", "assisted"), _AI_BADGE["assisted"])

            status_str = (
                "Graded" if a.get("score") is not None else
                "Pending review" if submitted else
                ("Past due" if (deadlines_on and due and now > due) else "Open")
            )
            rows.append({
                "Title": a["title"],
                "Type": a["type"],
                "AI": policy.get("level", "assisted"),
                "Score": f"{score}/{max_s}" if a.get("score") is not None else "--",
                "Grade": grade if a.get("score") is not None else "--",
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

section_divider("Download Transcript")
help_button("transcript-download")

def build_transcript_csv():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Student", student_name])
    writer.writerow(["GPA", f"{gpa:.2f}"])
    writer.writerow(["Verified Credits", credits])
    writer.writerow(["Activity Credits", activity_credits])
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
        "verified_credits": credits,
        "activity_credits": activity_credits,
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

section_divider("Degree Progress")
help_button("degree-eligibility")

_DEGREE_COLOURS = {
    "Certificate": "#40dc80",
    "Associate": "#00d4ff",
    "Bachelor": "#8080ff",
    "Master": "#ffd700",
    "Doctorate": "#e04040",
}

for degree, info in DEGREE_TRACKS.items():
    credit_pct = min(credits / info["min_credits"], 1.0)
    hours_needed = info.get("min_hours", info["min_credits"] * 45)
    gpa_ok = gpa >= info["min_gpa"]
    unlocked = degree in eligible
    colour = _DEGREE_COLOURS.get(degree, "#8080ff") if unlocked else "#303050"

    bar_fill = int(credit_pct * 30)
    bar_empty = 30 - bar_fill
    bar = "\u2588" * bar_fill + "\u2591" * bar_empty

    gpa_marker = "[GPA OK]" if gpa_ok else f"[GPA: need {info['min_gpa']:.1f}]"
    status_marker = "[ELIGIBLE]" if unlocked else "[LOCKED]"
    course_marker = f"[Courses {academic_summary['completed_courses']}/{info['min_courses']}]"
    assess_marker = f"[Assessments {academic_summary['verified_assessments']}/{info['min_verified_assessments']}]"

    st.markdown(
        f"<div style='font-family:monospace;margin:4px 0;'>"
        f"<span style='color:{colour};font-weight:bold;'>{degree:<12}</span>  "
        f"<span style='color:#404060;'>[{bar}]</span>  "
        f"<span style='color:#a0a0c0;font-size:0.85rem;'>"
        f"{credits:.1f}/{info['min_credits']} verified cr  "
        f"({academic_summary['hours_logged']:.0f}/{hours_needed:.0f} hrs)  "
        f"{gpa_marker}  "
        f"{course_marker}  "
        f"{assess_marker}  "
        f"<span style='color:{colour};'>{status_marker}</span>"
        f"</span></div>",
        unsafe_allow_html=True,
    )

# Time-to-degree estimate
section_divider("Time-to-Degree Estimate")
target_degree = st.selectbox("Target Degree", list(DEGREE_TRACKS.keys()), index=2)
estimate = time_to_degree_estimate(target_degree)
if estimate:
    e1, e2, e3 = st.columns(3)
    with e1:
        stat_card("Credits Needed", f"{estimate['credits_needed']:.1f}", colour="#ff8c00")
    with e2:
        stat_card("Hours Remaining", f"{estimate['hours_needed']:.0f}", colour="#00d4ff")
    with e3:
        days = estimate["est_days_remaining"]
        if days > 0:
            stat_card("Est. Days Left", f"{days:.0f}", colour="#ffd700")
        else:
            stat_card("Est. Days Left", "-- (need more data)" if estimate["credits_earned"] == 0 else "0", colour="#40dc80")
    if not estimate["gpa_met"]:
        st.warning(f"GPA of {gpa:.2f} is below the {DEGREE_TRACKS[target_degree]['min_gpa']:.1f} minimum for {target_degree}.")
