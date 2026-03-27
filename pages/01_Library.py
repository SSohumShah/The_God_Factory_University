"""Library page entrypoint. Delegates rendering to modular child tabs."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_all_courses
from core.ui_mode import require_ui_mode
from pages.library.alignment import render_alignment_tab
from pages.library.build import render_build_tab
from pages.library.explore import render_explore_tab
from pages.library.map_view import render_course_map
from pages.library.media_setup import render_media_sources_tab
from pages.library.services import course_index, course_summary, data_dict, matches_query, split_root_courses
from ui.theme import gf_header, help_button, inject_theme, section_divider

inject_theme()
require_ui_mode(("builder", "operator"), "Course Library")
gf_header("Library", "Explore courses first. Build and advanced tools are separated below.")
help_button("browsing-courses")

section_divider("Courses")
st.markdown(
    "Start with **Explore** to find what to study. "
    "Use **Build & Import** only when creating or editing courses."
)

all_courses = get_all_courses()
if not all_courses:
    st.info("No courses yet. Import one in Build & Import, or use Professor AI to generate one.")
    st.stop()

root_courses, sub_course_map = split_root_courses(all_courses)
root_index = course_index(root_courses, sub_course_map)


tab_explore, tab_build, tab_map, tab_alignment, tab_media = st.tabs(
    ["Explore", "Build & Import", "Course Map", "Curriculum Alignment", "Media Sources"]
)

with tab_explore:
    render_explore_tab(root_index, matches_query)

with tab_build:
    render_build_tab(root_index, data_dict)

with tab_map:
    render_course_map(
        root_courses,
        sub_course_map,
        lambda c, m: course_summary(c, m),
    )

with tab_alignment:
    render_alignment_tab(ROOT / "data" / "curriculum")

with tab_media:
    render_media_sources_tab()
