"""Student-friendly Explore tab for the Library page."""
from __future__ import annotations

import json

import streamlit as st

from core.content_log import get_covered_topics, get_level_count, log_generated_content
from core.database import get_lectures, get_modules, get_progress, get_setting, bulk_import_json
from core.db_scribe import level_scribe_complete, get_scribe_status_for_level, SCRIBE_MIN_WORDS
from llm.token_planner import quick_token_credit_estimate
from ui.theme import progress_badge, section_divider


def _generate_next_level(course: dict, children: list[dict]) -> None:
    """Generate the next enrichment course in sequence for *course*."""
    from llm.professor import Professor

    root_id = course.get("parent_course_id") or course["id"]
    existing_titles = [c["title"] for c in children]
    prev_level = get_level_count(root_id)
    next_level = max(len(children) + 1, prev_level + 1)
    parent_title = course["title"]
    subject = course.get("subject_id", parent_title)
    prefs = get_setting("student_preferences", "")

    # Build full covered-topics list from persistent log
    covered = get_covered_topics(root_id)
    for t in existing_titles:
        if t not in covered:
            covered.append(t)
    covered_note = ""
    if covered:
        _topics_str = ", ".join(covered[:80])
        covered_note = (
            f"Topics and concepts already covered across ALL previous levels: {_topics_str}. "
            "Do NOT repeat ANY of these — assume the student has mastered all of them."
        )

    pref_note = f"\nStudent learning preferences: {prefs}" if prefs else ""

    topic = (
        f"Level {next_level} continuation of '{parent_title}' (subject: {subject}). "
        f"This is an advanced depth course building on level {next_level - 1}. "
        f"{covered_note}"
        f"{pref_note} "
        f"Generate genuinely new content at increased difficulty — do not restate fundamentals."
    )

    status_box = st.empty()
    bar = st.progress(0)

    def _prog(msg: str) -> None:
        status_box.caption(f"Professor: {msg}")

    try:
        prof = Professor(session_id=f"next-level-{course['id']}")
        result = prof.chunked_curriculum(topic, level="advanced", lectures_per_module=3,
                                         progress_callback=_prog)
        parsed = result.parsed_json if hasattr(result, "parsed_json") and result.parsed_json else {}
        if isinstance(parsed, str):
            parsed = json.loads(parsed)

        bar.progress(0.8)
        if parsed:
            parsed["parent_course_id"] = course["id"]
            imported, errors = bulk_import_json(parsed)
            # Log generated topics for future repetition prevention
            new_topics = [parsed.get("title", "")]
            for m in parsed.get("modules", []):
                new_topics.append(m.get("title", ""))
                for lec in m.get("lectures", []):
                    new_topics.append(lec.get("title", ""))
                    new_topics.extend(lec.get("learning_objectives", []))
            log_generated_content(root_id, parsed.get("course_id", ""), "next_level",
                                  [t for t in new_topics if t], next_level)
            bar.progress(1.0)
            status_box.empty()
            st.success(
                f"Level {next_level} course '{parsed.get('title', '?')}' created! "
                f"({imported} objects) — find it in Course Map under this course."
            )
        else:
            status_box.empty()
            bar.empty()
            st.error("Professor could not generate next level course.")
    except Exception as exc:
        status_box.empty()
        bar.empty()
        st.error(f"Next level generation failed: {exc}")


def _ask_professor_inline(course: dict, question: str) -> None:
    """Inline one-shot Professor answer scoped to a course."""
    from llm.providers import simple_complete, cfg_from_settings

    cfg = cfg_from_settings()
    prompt = (
        f"You are a university professor. The student is studying '{course['title']}' "
        f"(ID: {course['id']}). Course description: {course.get('description', 'N/A')}.\n\n"
        f"Student question: {question}\n\n"
        f"Answer concisely and helpfully. Do NOT use markdown formatting."
    )
    try:
        with st.spinner("Professor is thinking..."):
            answer = simple_complete(cfg, prompt)
        st.info(answer)
    except Exception as exc:
        st.error(f"Professor offline: {exc}")


def _render_lesson_preview(modules: list[dict], max_rows: int = 12) -> None:
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


def render_explore_tab(course_index: list[dict], matches_query_fn) -> None:
    section_divider("Explore")
    st.markdown("Pick a course card. Start with **Open in Study**. You can always come back here.")

    q1, q2, q3 = st.columns([2, 1, 1])
    with q1:
        query = st.text_input("Find a course", placeholder="Type course name or code...")
    with q2:
        progress_filter = st.selectbox("Progress", ["All", "Not Started", "In Progress", "Completed"])
    with q3:
        readiness_filter = st.selectbox("AI Readiness", ["All", "Ready", "Needs Work"])

    filtered = []
    for item in course_index:
        course = item["course"]
        summary = item["summary"]
        if not matches_query_fn(course, query):
            continue
        pct = summary["completion_pct"]
        if progress_filter == "Not Started" and pct != 0:
            continue
        if progress_filter == "In Progress" and (pct <= 0 or pct >= 100):
            continue
        if progress_filter == "Completed" and pct < 100:
            continue
        ready = summary["readiness"]["ai_ready"]
        if readiness_filter == "Ready" and not ready:
            continue
        if readiness_filter == "Needs Work" and ready:
            continue
        filtered.append(item)

    st.caption(f"Showing {len(filtered)} of {len(course_index)} root courses")
    if not filtered:
        st.info("No courses matched your filters.")
        return

    for item in filtered:
        course = item["course"]
        summary = item["summary"]
        ready = summary["readiness"]["ai_ready"]
        children = summary["children"]

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f"### {course['title']}")
                st.caption(course["id"])
                st.caption(course.get("description") or "No description yet.")
            with c2:
                st.metric("Lessons", summary["total_lectures"])
                st.metric("Progress", f"{summary['completion_pct']:.0f}%")
            with c3:
                st.metric("Credits", course["credits"])
                _token_target = int(get_setting("token_target", "50000"))
                _tce = quick_token_credit_estimate(summary["total_lectures"], _token_target)
                st.caption(_tce["label"])
                st.metric("Sub-Courses", len(children))

            a1, a2, a3, a4 = st.columns(4)
            with a1:
                st.page_link("pages/02_Lecture_Studio.py", label="Open in Study")
            with a2:
                st.page_link("pages/03_Professor_AI.py", label="Ask Professor")
            with a3:
                st.caption("Status: " + ("AI-ready" if ready else "Needs data"))
            with a4:
                _next_key = f"next_level_{course['id']}"
                _cur_depth = course.get("depth_level", 0)
                _scribe_ok = level_scribe_complete(course["id"], _cur_depth)
                if _scribe_ok:
                    if st.button("Next Level →", key=_next_key, use_container_width=True):
                        _generate_next_level(course, children)
                else:
                    _ss = get_scribe_status_for_level(course["id"], _cur_depth)
                    st.button("Next Level →", key=_next_key, use_container_width=True,
                              disabled=True)
                    st.caption(
                        f"Scribe {_ss['words_submitted']:,}/{SCRIBE_MIN_WORDS:,} words "
                        f"at level {_cur_depth} — open Lecture Studio to submit"
                    )

            with st.expander("Show Lessons"):
                _render_lesson_preview(summary["modules"], max_rows=12)
            if children:
                with st.expander("Show Sub-Courses"):
                    for child in children:
                        st.markdown(f"- {child['title']} ({child['id']})")

            # Inline Professor AI mini-chat per course
            with st.expander("Ask Professor about this course"):
                _chat_key = f"prof_q_{course['id']}"
                _q = st.text_input(
                    "Question", key=_chat_key,
                    placeholder=f"Ask about {course['title']}...",
                    label_visibility="collapsed",
                )
                if _q and st.button("Ask", key=f"prof_go_{course['id']}"):
                    _ask_professor_inline(course, _q)
