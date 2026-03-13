"""
Help — Comprehensive interconnected help system for Arcane University.
Every feature links here with a topic anchor for contextual navigation.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.help_registry import get_all_help, get_help
from ui.theme import inject_theme, arcane_header, rune_divider

inject_theme()
arcane_header("Help", "Your guide to every feature of Arcane University.")

# ─── Check for topic query param for contextual navigation ────────────────────
params = st.query_params
topic = params.get("topic", "")

if topic:
    entry = get_help(topic)
    if entry:
        st.info(f"Showing help for: {entry['title']}")
        rune_divider(entry["title"])
        st.markdown(entry["text"])
        st.markdown("---")
        st.markdown("**Browse all help topics below.**")
    else:
        st.warning(f"Help topic '{topic}' not found. Showing all topics.")

# ─── Table of Contents ────────────────────────────────────────────────────────
rune_divider("TABLE OF CONTENTS")

entries = get_all_help()

# Group entries by prefix
groups = {}
for anchor, entry in entries.items():
    prefix = anchor.split("-")[0].title()
    # Map prefixes to friendly names
    name_map = {
        "Dashboard": "Dashboard",
        "System": "Dashboard",
        "Xp": "XP & Levels",
        "Importing": "Library",
        "Course": "Library",
        "Browsing": "Library",
        "Deleting": "Library",
        "Playing": "Lecture Studio",
        "Rendering": "Lecture Studio",
        "Scene": "Lecture Studio",
        "Assignment": "Lecture Studio",
        "Professor": "Professor AI",
        "Generate": "Professor AI",
        "Grade": "Grades",
        "Create": "Professor AI",
        "Research": "Professor AI",
        "Reordering": "Timeline Editor",
        "Exporting": "Timeline Editor",
        "Batch": "Batch Render",
        "Gpa": "Grades",
        "Degree": "Grades",
        "Transcript": "Grades",
        "Achievement": "Achievements",
        "Level": "Achievements",
        "Voice": "Settings",
        "Binaural": "Settings",
        "Llm": "Settings & LLM",
        "Video": "Settings",
        "Deadline": "Settings",
        "Diagnostics": "Diagnostics",
        "Compile": "Diagnostics",
    }
    group_name = name_map.get(prefix, "General")
    groups.setdefault(group_name, []).append(entry)

# Sidebar quick links
with st.sidebar:
    st.markdown("### HELP SECTIONS")
    for group_name in groups:
        st.markdown(f"- {group_name}")

# Render all groups
for group_name, group_entries in groups.items():
    rune_divider(group_name)
    for entry in group_entries:
        with st.expander(f"  {entry['title']}", expanded=(entry["anchor"] == topic)):
            st.markdown(entry["text"])
            st.caption(f"Help ID: {entry['anchor']}")

# ─── Quick links ──────────────────────────────────────────────────────────────
rune_divider("QUICK LINKS")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Getting Started**")
    st.markdown("- [Dashboard Overview](?topic=dashboard-overview)")
    st.markdown("- [Import a Course](?topic=importing-courses)")
    st.markdown("- [Render a Lecture](?topic=rendering-lecture)")
with col2:
    st.markdown("**Academic**")
    st.markdown("- [GPA & Grading](?topic=gpa-calculation)")
    st.markdown("- [Degree Eligibility](?topic=degree-eligibility)")
    st.markdown("- [XP & Levels](?topic=xp-and-levels)")
with col3:
    st.markdown("**Configuration**")
    st.markdown("- [Voice Setup](?topic=voice-settings)")
    st.markdown("- [LLM Provider](?topic=llm-provider-settings)")
    st.markdown("- [Video Settings](?topic=video-settings)")
