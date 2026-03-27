"""Advanced course hierarchy map tab for the Library page."""
from __future__ import annotations

import streamlit as st

from core.database import get_lectures, get_pacing_for_course, get_progress
from ui.theme import progress_badge, section_divider


def _render_lesson_list(modules: list[dict], max_rows: int = 10) -> None:
    shown = 0
    for module in modules:
        if shown >= max_rows:
            break
        lectures = get_lectures(module["id"])
        st.markdown(f"**{module['title']}**")
        for lecture in lectures:
            progress = get_progress(lecture["id"])
            badge = progress_badge(progress.get("status", "not_started"))
            st.markdown(f"- {lecture['title']} {badge}", unsafe_allow_html=True)
            shown += 1
            if shown >= max_rows:
                break


def render_course_map(root_courses: list[dict], sub_course_map: dict[str, list[dict]], course_summary_fn) -> None:
    section_divider("Course Map")
    st.markdown("Full hierarchy view for advanced planning.")

    def _render(course: dict, indent: int = 0) -> None:
        summary = course_summary_fn(course, sub_course_map)
        children = summary["children"]
        readiness = summary["readiness"]
        label = (
            f"{'  ' * indent}{course['id']}  {course['title']} "
            f"({summary['total_lectures']} lessons, {course['credits']} cr)"
        )
        if children:
            label += f"  [{len(children)} sub-courses]"
        if readiness["ai_ready"]:
            label += "  [AI-ready]"

        # Only top-level courses get expanders; children use indented containers
        if indent == 0:
            with st.expander(label, expanded=False):
                _render_course_body(course, summary, children, indent)
        else:
            # Indented sub-course rendered flat (no nested expander)
            indent_px = indent * 24
            st.markdown(
                f"<div style='border-left:2px solid #00d4ff44;padding:6px 12px;"
                f"margin-left:{indent_px}px;margin-bottom:4px;background:#0a1020;'>"
                f"<span style='color:#00d4ff;font-family:monospace;font-size:0.85rem;'>"
                f"↳ {course['title']}</span>"
                f"<span style='color:#606080;font-size:0.78rem;'>"
                f"  ({summary['total_lectures']} lessons, {course['credits']} cr) "
                f"| {summary['completion_pct']:.0f}% complete"
                f"</span></div>",
                unsafe_allow_html=True,
            )
            # Show child sub-courses recursively (still flat, just more indent)
            for child in children:
                _render(child, indent + 1)

    def _render_course_body(course, summary, children, indent):
        st.caption(course.get("description") or "No description")
        st.caption(
            f"Completion: {summary['completion_pct']:.0f}% | "
            f"Pacing: {get_pacing_for_course(course['id'])} | "
            f"Depth: {course.get('depth_level') or 0}"
        )
        if course.get("parent_course_id"):
            st.caption(f"Parent: {course['parent_course_id']}")
        _render_lesson_list(summary["modules"], max_rows=10)
        for child in children:
            _render(child, indent + 1)

    for course in root_courses:
        _render(course)
