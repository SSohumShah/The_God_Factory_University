"""
Help — Comprehensive interconnected help system for The God Factory University.
Every feature links here with a topic anchor for contextual navigation.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.help_registry import get_all_help, get_help
from ui.theme import inject_theme, gf_header, section_divider

inject_theme()
gf_header("Help", "Your guide to every feature of The God Factory University.")

# ─── Check for topic query param for contextual navigation ────────────────────
params = st.query_params
topic = params.get("topic", "")

if topic:
    entry = get_help(topic)
    if entry:
        st.info(f"Showing help for: {entry['title']}")
        section_divider(entry["title"])
        st.markdown(entry["text"])
        st.markdown("---")
        st.markdown("**Browse all help topics below.**")
    else:
        st.warning(f"Help topic '{topic}' not found. Showing all topics.")

# ─── End-to-End Tutorial ─────────────────────────────────────────────────────
section_divider("END-TO-END TUTORIAL")

with st.expander("Complete Walkthrough — New User Start to Finish", expanded=not topic):
    st.markdown("""
### Welcome to The God Factory University

This is a self-contained AI-powered university application. It combines **course
management**, **AI tutoring**, **video lecture generation**, **grading**, and
**gamification** into a single offline-capable desktop app.

---

### Step 1: Set Up Your AI Provider

Before using AI features (Professor, curriculum generation, grading), configure
an LLM provider:

1. Go to **LLM Setup Wizard** in the sidebar
2. Choose **Local** (free, runs on your machine) or **Cloud** (API key needed)
3. For the fastest free start: choose **Ollama**, install it, run `ollama pull llama3.2`
4. The wizard auto-detects your setup and tests the connection

[Set up LLM now](?topic=llm-setup-wizard)

---

### Step 2: Import or Generate a Course

**Option A — Import existing JSON:**
1. Go to **Library** > expand **BULK IMPORT**
2. Paste course JSON (see `schemas/SCHEMA_GUIDE.md` for the format)
3. Click Import — courses, modules, and lectures appear instantly

**Option B — AI-generate a course:**
1. Go to **Professor AI** > **Generate Curriculum** tab
2. Enter a topic, choose difficulty level, set lectures per module
3. The AI generates a complete course JSON — review and import it

[Import courses](?topic=importing-courses) · [Generate curriculum](?topic=generate-curriculum)

---

### Step 3: Study with the Professor

1. Go to **Professor AI** > **Chat** tab
2. Ask questions about any topic — the professor uses Socratic method
3. Use **Create Quiz** to self-test on any lecture material
4. Use **Research Rabbit Hole** to explore topics deeply
5. Use **Grade Work** to submit essays or code for AI feedback

[Chat with Professor](?topic=professor-chat) · [Create quizzes](?topic=create-quiz)

---

### Step 4: Render & Watch Video Lectures

1. Go to **Lecture Studio**, select a course, module, and lecture
2. Click **Render Full Lecture** — generates TTS narration, animated visuals,
   binaural beats, and encodes to MP4
3. Watch the video directly in the browser
4. Mark lectures as complete to earn XP

[Render lectures](?topic=rendering-lecture) · [Batch render](?topic=batch-render)

---

### Step 5: Track Your Progress

- **Grades** page: View GPA, letter grades, degree eligibility, download transcripts
- **Achievements** page: Unlock 17 milestones through activity
- **Statistics** page: Charts of daily activity, grade distribution, study hours
- **Profile** page: Set your name, grade level, learning style, study pace
- **Qualifications** page: Track progress toward real-world benchmark equivalencies

[GPA & Grades](?topic=gpa-calculation) · [Achievements](?topic=achievement-system) ·
[Statistics](?topic=statistics-dashboard)

---

### Step 6: Advanced Features

- **Timeline Editor**: Reorder and customize lecture video scenes
- **Placement Testing**: Take adaptive exams to find your starting level
- **Test Prep**: Practice for GED, SAT, ACT, GRE with timed sessions
- **Programs**: Browse and enroll in structured degree programs
- **Agent**: Automate complex tasks (e.g., create entire course catalogs)

[Timeline Editor](?topic=reordering-scenes) · [Placement Tests](?topic=placement-testing) ·
[Agent](?topic=agent-dashboard)

---

### Settings & Maintenance

- **Settings**: Voice selection (13 neural voices), binaural beat presets,
  video quality (FPS/resolution), deadline toggles
- **Diagnostics**: System health checks, dependency versions, LLM connectivity test,
  compile check for all Python files
- **LLM Setup Wizard**: Change or reconfigure your AI provider at any time

[Settings](?topic=voice-settings) · [Diagnostics](?topic=diagnostics-page)
""")

# ─── Table of Contents ────────────────────────────────────────────────────────
section_divider("ALL HELP TOPICS")

entries = get_all_help()

# Group entries by prefix — comprehensive mapping
groups = {}
for anchor, entry in entries.items():
    prefix = anchor.split("-")[0].title()
    name_map = {
        "Dashboard": "Dashboard",
        "System": "Dashboard",
        "Xp": "XP & Progression",
        "First": "Getting Started",
        "Importing": "Library",
        "Course": "Library",
        "Browsing": "Library",
        "Deleting": "Library",
        "Playing": "Lecture Studio",
        "Rendering": "Lecture Studio",
        "Render": "Lecture Studio",
        "Scene": "Lecture Studio",
        "Assignment": "Lecture Studio",
        "Professor": "Professor AI",
        "Generate": "Professor AI",
        "Create": "Professor AI",
        "Research": "Professor AI",
        "Reordering": "Timeline Editor",
        "Exporting": "Timeline Editor",
        "Batch": "Batch Render",
        "Prompt": "Batch Render",
        "Gpa": "Grades & Transcript",
        "Grade": "Grades & Transcript",
        "Degree": "Grades & Transcript",
        "Transcript": "Grades & Transcript",
        "Achievement": "Achievements & XP",
        "Level": "Achievements & XP",
        "Voice": "Settings",
        "Binaural": "Settings",
        "Video": "Settings",
        "Deadline": "Settings",
        "Llm": "LLM Setup",
        "Diagnostics": "Diagnostics",
        "Compile": "Diagnostics",
        "Placement": "Placement & Testing",
        "Test": "Placement & Testing",
        "Programs": "Programs & Degrees",
        "Student": "Student Profile",
        "Statistics": "Statistics",
        "Agent": "Agent",
        "Qualifications": "Qualifications",
    }
    group_name = name_map.get(prefix, "General")
    groups.setdefault(group_name, []).append(entry)

# Ordered group display
GROUP_ORDER = [
    "Getting Started", "Dashboard", "Library", "Lecture Studio",
    "Professor AI", "Timeline Editor", "Batch Render",
    "Grades & Transcript", "Achievements & XP", "XP & Progression",
    "Settings", "LLM Setup", "Diagnostics",
    "Placement & Testing", "Programs & Degrees", "Student Profile",
    "Statistics", "Agent", "Qualifications", "General",
]

# Sidebar quick links
with st.sidebar:
    st.markdown("### HELP SECTIONS")
    for g in GROUP_ORDER:
        if g in groups:
            st.markdown(f"- {g}")

# Render all groups in order
for group_name in GROUP_ORDER:
    if group_name not in groups:
        continue
    section_divider(group_name)
    for entry in groups[group_name]:
        with st.expander(f"  {entry['title']}", expanded=(entry["anchor"] == topic)):
            st.markdown(entry["text"])
            st.caption(f"Help ID: {entry['anchor']}")

# Any groups not in ORDER
for group_name, group_entries in groups.items():
    if group_name in GROUP_ORDER:
        continue
    section_divider(group_name)
    for entry in group_entries:
        with st.expander(f"  {entry['title']}", expanded=(entry["anchor"] == topic)):
            st.markdown(entry["text"])
            st.caption(f"Help ID: {entry['anchor']}")

# ─── Quick Reference ─────────────────────────────────────────────────────────
section_divider("QUICK REFERENCE")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Getting Started**")
    st.markdown("- [First Launch](?topic=first-launch)")
    st.markdown("- [LLM Setup Wizard](?topic=llm-setup-wizard)")
    st.markdown("- [Dashboard Overview](?topic=dashboard-overview)")
    st.markdown("- [Import a Course](?topic=importing-courses)")
    st.markdown("- [Render a Lecture](?topic=rendering-lecture)")
    st.markdown("- [Chat with Professor](?topic=professor-chat)")
with col2:
    st.markdown("**Academic Progress**")
    st.markdown("- [GPA & Grading](?topic=gpa-calculation)")
    st.markdown("- [Degree Eligibility](?topic=degree-eligibility)")
    st.markdown("- [XP & Levels](?topic=xp-and-levels)")
    st.markdown("- [Achievements](?topic=achievement-system)")
    st.markdown("- [Qualifications](?topic=qualifications-dashboard)")
    st.markdown("- [Statistics](?topic=statistics-dashboard)")
with col3:
    st.markdown("**Configuration & Tools**")
    st.markdown("- [Voice Settings](?topic=voice-settings)")
    st.markdown("- [LLM Providers](?topic=llm-provider-settings)")
    st.markdown("- [Video Settings](?topic=video-settings)")
    st.markdown("- [Agent Dashboard](?topic=agent-dashboard)")
    st.markdown("- [Placement Tests](?topic=placement-testing)")
    st.markdown("- [Diagnostics](?topic=diagnostics-page)")
