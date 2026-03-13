"""
Library page — browse courses, import new ones, manage curriculum.
"""

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    bulk_import_json, get_all_courses, get_modules, get_lectures,
    delete_course, get_progress, add_xp,
)
from ui.theme import inject_theme, arcane_header, rune_divider, progress_badge, play_sfx, help_button

inject_theme()
arcane_header("Library", "Your collection of courses and arcane knowledge.")
help_button("browsing-courses")

# ─── Bulk Import ─────────────────────────────────────────────────────────────
with st.expander("[ BULK IMPORT ] -- Paste JSON from LLM or file", expanded=False):
    help_button("importing-courses")
    st.markdown(
        "Paste any of: a single course object, a JSON array, "
        "or multiple newline-separated JSON objects. "
        "See `schemas/SCHEMA_GUIDE.md` for the prompt to give an LLM."
    )
    raw = st.text_area("JSON Input", height=200, placeholder='{"course_id": "...", "title": "...", "modules": [...]}')
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        import_clicked = st.button("Import", use_container_width=True)
    with btn_col2:
        validate_clicked = st.button("Validate Only (Dry Run)", use_container_width=True)
    if import_clicked or validate_clicked:
        if raw.strip():
            dry = validate_clicked
            with st.spinner("Validating..." if dry else "Importing..."):
                count, errors = bulk_import_json(raw.strip(), validate_only=dry)
            # Build structured import report
            report = {
                "mode": "dry_run" if dry else "import",
                "objects_processed": count,
                "errors": len(errors),
                "error_details": errors,
            }
            if count:
                if dry:
                    st.success(f"Validation passed for {count} object(s). Ready to import.")
                else:
                    play_sfx("success")
                    st.success(f"Imported {count} objects successfully.")
                    add_xp(count * 10, "Library import", "import")
            for e in errors:
                st.error(e)
            if errors or count:
                with st.expander("Import Report", expanded=bool(errors)):
                    st.json(report)
                    st.download_button(
                        "Download Report JSON",
                        json.dumps(report, indent=2),
                        file_name="import_report.json",
                        mime="application/json",
                    )
        else:
            st.warning("Paste some JSON first.")

rune_divider("Courses")

courses = get_all_courses()
if not courses:
    st.info("No courses yet. Import one above, or open Professor AI to generate one.")
    st.stop()

for i, course in enumerate(courses):
    modules = get_modules(course["id"])
    total_lectures = sum(len(get_lectures(m["id"])) for m in modules)

    with st.expander(f"  {course['id']}  {course['title']}  ({total_lectures} lectures, {course['credits']} cr)", expanded=False):
        col_a, col_b, col_c = st.columns([3, 1, 1])
        with col_a:
            st.caption(course.get("description") or "No description.")
            st.caption(f"Source: {course.get('source', 'imported')}")
        with col_b:
            st.metric("Credits", course["credits"])
        with col_c:
            if st.button("Delete", key=f"del_{course['id']}"):
                delete_course(course["id"])
                play_sfx("error")
                st.rerun()

        for module in modules:
            st.markdown(
                f"<div style='color:#ffd700;font-family:monospace;margin-top:10px;'>"
                f"  Module {module['order_index']+1}: {module['title']}</div>",
                unsafe_allow_html=True,
            )
            for lec in get_lectures(module["id"]):
                prog = get_progress(lec["id"])
                badge = progress_badge(prog.get("status", "not_started"))
                st.markdown(
                    f"<div style='font-family:monospace;padding:2px 20px;color:#b8b8d0;'>"
                    f"  ├ {lec['title']} &nbsp; {badge}</div>",
                    unsafe_allow_html=True,
                )
