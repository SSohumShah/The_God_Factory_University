"""
Achievements — badge gallery, XP history, level progression.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_all_achievements, get_xp_history, get_total_xp, get_level
from ui.theme import (
    inject_theme, arcane_header, rune_divider,
    achievement_card, xp_bar, level_badge, stat_card, help_button,
)

inject_theme()
arcane_header("Achievements", "Your record of conquest in the arcane order.")
help_button("achievement-system")

total_xp = get_total_xp()
level, level_name, xp_in_level, xp_for_next = get_level(total_xp)

lb1, lb2, lb3 = st.columns(3)
with lb1:
    level_badge(level, level_name)
with lb2:
    stat_card("Total XP", str(total_xp), colour="#ffd700")
with lb3:
    stat_card("Next Level in", f"{xp_for_next - xp_in_level} XP", colour="#00d4ff")

xp_bar(xp_in_level, xp_for_next)

# ─── Level progression ────────────────────────────────────────────────────────
rune_divider("Level Progression")
help_button("level-system")

LEVELS = [
    (0,     "Seeker",      "#808080"),
    (100,   "Initiate",    "#40dc80"),
    (300,   "Scholar",     "#00d4ff"),
    (700,   "Adept",       "#8080ff"),
    (1500,  "Sorcerer",    "#c060ff"),
    (3000,  "Sage",        "#ffd700"),
    (6000,  "Arcane",      "#ff8040"),
    (10000, "Grandmaster", "#ff4040"),
    (20000, "Luminary",    "#ff40c0"),
    (50000, "Archon",      "#ffffff"),
]

for i, (xp_req, name, colour) in enumerate(LEVELS):
    unlocked = total_xp >= xp_req
    is_current = level == i
    marker = "[ CURRENT ]" if is_current else ("[ UNLOCKED ]" if unlocked else "[ LOCKED ]")
    text_colour = colour if unlocked else "#303050"
    st.markdown(
        f"<div style='font-family:monospace;margin:2px 0;"
        f"{"background:#0e1230;border-left:3px solid " + colour + ";padding:4px 8px;" if is_current else "padding:4px 8px;"}'>"
        f"<span style='color:{text_colour};font-weight:{"bold" if is_current else "normal"};'>"
        f"Lv {i:2d}  {name:<14}  {xp_req:>6} XP  {marker}</span></div>",
        unsafe_allow_html=True,
    )

# ─── Achievement badges ───────────────────────────────────────────────────────
rune_divider("Achievement Badges")
help_button("achievement-system")

ALL_BADGES = [
    {"id": "first_lecture",    "title": "First Steps",        "desc": "Complete your first lecture.",           "category": "progress"},
    {"id": "first_curriculum", "title": "Architect",          "desc": "Generate your first AI curriculum.",     "category": "creation"},
    {"id": "scholar",          "title": "Scholar",            "desc": "Complete 10 lectures.",                  "category": "progress"},
    {"id": "sage",             "title": "Sage",               "desc": "Complete 25 lectures.",                  "category": "progress"},
    {"id": "grandmaster",      "title": "Grandmaster",        "desc": "Complete 50 lectures.",                  "category": "progress"},
    {"id": "perfect_score",    "title": "Perfect Score",      "desc": "Achieve 100% on any assignment.",        "category": "grades"},
    {"id": "gpa_honor",        "title": "Honor Roll",         "desc": "Maintain GPA above 3.5.",                "category": "grades"},
    {"id": "night_owl",        "title": "Night Owl",          "desc": "Study after midnight.",                  "category": "habits"},
    {"id": "rabbit_hole",      "title": "Deep Diver",         "desc": "Use Research Rabbit Hole 5 times.",      "category": "exploration"},
    {"id": "batch_render",     "title": "Auteur",             "desc": "Complete a batch render.",               "category": "creation"},
    {"id": "certificate",      "title": "Certified",          "desc": "Earn Certificate eligibility.",          "category": "degree"},
    {"id": "associate",        "title": "Associate",          "desc": "Earn Associate degree eligibility.",     "category": "degree"},
    {"id": "bachelor",         "title": "Bachelor",           "desc": "Earn Bachelor degree eligibility.",      "category": "degree"},
    {"id": "master",           "title": "Master",             "desc": "Earn Master degree eligibility.",        "category": "degree"},
    {"id": "doctorate",        "title": "Doctor",             "desc": "Earn Doctorate eligibility.",            "category": "degree"},
    {"id": "first_quiz",       "title": "Quiz Taker",         "desc": "Take your first generated quiz.",        "category": "assessment"},
    {"id": "streak_7",         "title": "Relentless",         "desc": "Study 7 days in a row.",                 "category": "habits"},
    {"id": "xp_1000",          "title": "Thousand Points",    "desc": "Earn 1,000 XP total.",                   "category": "xp"},
    {"id": "xp_10000",         "title": "Ten Thousand",       "desc": "Earn 10,000 XP total.",                  "category": "xp"},
    {"id": "all_courses",      "title": "Completionist",      "desc": "Finish every lecture in every course.",  "category": "progress"},
]

unlocked_ids = {a["id"] for a in get_all_achievements()}
categories = sorted(set(b["category"] for b in ALL_BADGES))
selected_cat = st.selectbox("Filter by category", ["all"] + categories)

filtered = ALL_BADGES if selected_cat == "all" else [b for b in ALL_BADGES if b["category"] == selected_cat]
cols = st.columns(3)
for i, badge in enumerate(filtered):
    unlocked = badge["id"] in unlocked_ids
    with cols[i % 3]:
        achievement_card(badge["title"], badge["desc"], badge["category"], unlocked)

# ─── XP event history ─────────────────────────────────────────────────────────
rune_divider("XP History")
history = get_xp_history(50)
if history:
    for ev in history:
        import datetime
        ts = datetime.datetime.fromtimestamp(ev["occurred_at"]).strftime("%Y-%m-%d %H:%M")
        st.markdown(
            f"<span style='font-family:monospace;color:#606080;font-size:0.82rem;'>"
            f"{ts}  </span>"
            f"<span style='font-family:monospace;color:#ffd700;'>"
            f"+{ev['xp_gained']:>5} XP  </span>"
            f"<span style='font-family:monospace;color:#a0a0c0;'>{ev['description']}</span>",
            unsafe_allow_html=True,
        )
else:
    st.info("No XP events recorded yet. Complete lectures to start earning XP.")
