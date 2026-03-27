"""
Student Profile — personal info, learning preferences, session history.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_setting, set_setting, get_xp, get_level, get_grade_levels,
    get_enrollment_date, time_to_degree_days, compute_gpa, credits_earned, tx,
    get_academic_progress_summary,
)
from core import db_activity
from ui.theme import inject_theme, gf_header, section_divider, stat_card, help_button

inject_theme()
gf_header("Student Profile", "Your academic identity and preferences.")
help_button("student-profile")

# ─── Basic Info ───────────────────────────────────────────────────────────────
section_divider("Identity")

name = get_setting("student_name", "Scholar")
new_name = st.text_input("Display Name", value=name)
if new_name != name:
    set_setting("student_name", new_name)
    st.success("Name updated!")

# Grade Level Selection
grade_levels = get_grade_levels()
level_names = [g["name"] for g in grade_levels]
current_gl = get_setting("grade_level", "")
current_idx = 0
for i, g in enumerate(grade_levels):
    if g["id"] == current_gl:
        current_idx = i
        break

if level_names:
    sel = st.selectbox("Grade Level", range(len(level_names)), index=current_idx,
                       format_func=lambda i: level_names[i])
    new_gl = grade_levels[sel]["id"]
    if new_gl != current_gl:
        set_setting("grade_level", new_gl)
        st.success("Grade level updated!")

# ─── Learning Preferences ────────────────────────────────────────────────────
section_divider("Learning Preferences")

STYLES = ["Visual", "Auditory", "Reading/Writing", "Kinesthetic"]
current_style = db_activity.get_profile("learning_style", tx, default="Visual")
style_idx = STYLES.index(current_style) if current_style in STYLES else 0
new_style = st.selectbox("Preferred Learning Style", STYLES, index=style_idx)
if new_style != current_style:
    db_activity.set_profile("learning_style", new_style, tx)
    st.success("Learning style updated!")

pace = db_activity.get_profile("study_pace", tx, default="moderate")
PACES = ["relaxed", "moderate", "intensive"]
pace_idx = PACES.index(pace) if pace in PACES else 1
new_pace = st.selectbox("Study Pace", PACES, index=pace_idx,
                        format_func=lambda p: p.capitalize())
if new_pace != pace:
    db_activity.set_profile("study_pace", new_pace, tx)

# ─── Academic Summary ─────────────────────────────────────────────────────────
section_divider("Academic Summary")

total_xp = get_xp()
lvl_idx, lvl_name, xp_in, xp_next = get_level(total_xp)
gpa, _ = compute_gpa()
creds = credits_earned()
academic_summary = get_academic_progress_summary()
enroll_date = get_enrollment_date()
days = time_to_degree_days()

c1, c2, c3, c4 = st.columns(4)
with c1:
    stat_card("Rank", lvl_name, colour="#c060ff")
with c2:
    stat_card("XP", str(total_xp), colour="#ffd700")
with c3:
    stat_card("GPA", f"{gpa:.2f}", colour="#40dc80")
with c4:
    stat_card("Verified Credits", str(creds), colour="#00d4ff")

st.markdown(f"**Enrolled since:** {enroll_date} ({days} days)")
st.caption(f"Activity credits: {academic_summary['activity_credits']:.2f}")

# ─── Study Streak ─────────────────────────────────────────────────────────────
section_divider("Study Streak")

streak = int(get_setting("streak_days", "0"))
last = get_setting("streak_last_date", "—")
st.markdown(f"[STREAK] **{streak}** consecutive day{'s' if streak != 1 else ''} (last active: {last})")
bonus = min(streak * 5, 50)
st.caption(f"Current streak bonus: +{bonus}% XP")
