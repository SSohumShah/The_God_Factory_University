"""Build & Import tab for the Library page."""
from __future__ import annotations

import json

import streamlit as st

from core.database import (
    BLOOMS_LEVELS,
    add_xp,
    course_credit_hours,
    delete_course,
    get_assessment_hours,
    get_competency_profile,
    hours_to_credits,
    upsert_course,
)
from ui.theme import play_sfx, section_divider


def render_import_panel() -> None:
    with st.expander("JSON Import", expanded=False):
        st.markdown(
            "Paste any of: a single course object, a JSON array, "
            "or multiple newline-separated JSON objects. "
            "See `schemas/SCHEMA_GUIDE.md` for the prompt to give an LLM."
        )
        raw = st.text_area("JSON Input", height=220, placeholder='{"course_id": "...", "title": "...", "modules": [...]}')
        b1, b2 = st.columns(2)
        with b1:
            import_clicked = st.button("Import", use_container_width=True)
        with b2:
            validate_clicked = st.button("Validate Only (Dry Run)", use_container_width=True)
        if import_clicked or validate_clicked:
            if not raw.strip():
                st.warning("Paste some JSON first.")
                return
            from core.database import bulk_import_json

            dry = validate_clicked
            with st.spinner("Validating..." if dry else "Importing..."):
                count, errors = bulk_import_json(raw.strip(), validate_only=dry)

            report = {
                "mode": "dry_run" if dry else "import",
                "objects_processed": count,
                "errors": len(errors),
                "error_details": errors,
            }
            if count:
                if dry:
                    st.success(f"Validation passed for {count} object(s).")
                else:
                    play_sfx("success")
                    st.success(f"Imported {count} objects successfully.")
                    add_xp(count * 10, "Library import", "import")
            for err in errors:
                st.error(err)
            if errors or count:
                with st.expander("Import Report", expanded=bool(errors)):
                    st.json(report)
                    st.download_button(
                        "Download Report JSON",
                        json.dumps(report, indent=2),
                        file_name="import_report.json",
                        mime="application/json",
                    )


def _render_build_controls(course: dict, summary: dict, data_dict_fn) -> None:
    course_id = course["id"]
    depth = course.get("depth_level") or 0
    pacing = course.get("pacing") or "standard"
    data = data_dict_fn(course)

    p1, p2 = st.columns(2)
    with p1:
        new_pacing = st.selectbox(
            "Pacing",
            ["fast", "standard", "slow"],
            index=["fast", "standard", "slow"].index(pacing),
            key=f"pace_{course_id}",
        )
        if st.button("Save Pacing", key=f"save_pacing_{course_id}"):
            upsert_course(
                course_id,
                course["title"],
                course.get("description", ""),
                course["credits"],
                data,
                course.get("source", "imported"),
                parent_course_id=course.get("parent_course_id"),
                depth_level=depth,
                depth_target=course.get("depth_target") or 0,
                pacing=new_pacing,
                is_jargon_course=course.get("is_jargon_course") or 0,
                jargon=course.get("jargon"),
            )
            st.success("Pacing updated.")
            st.rerun()
    with p2:
        if st.button("Decompose", key=f"decompose_{course_id}", use_container_width=True):
            from llm.professor import Professor

            prof = Professor(session_id="library_decompose")
            with st.spinner("Generating sub-courses..."):
                response = prof.decompose_course(course_id)
            if response.parsed_json and response.parsed_json.get("sub_courses_created"):
                st.success(f"Created {response.parsed_json['sub_courses_created']} sub-courses.")
                st.rerun()
            else:
                for warning in response.warnings:
                    st.warning(warning)

        if st.button("Generate Jargon Course", key=f"jargon_{course_id}", use_container_width=True):
            from llm.professor import Professor

            prof = Professor(session_id="library_jargon")
            with st.spinner("Extracting terminology..."):
                response = prof.generate_jargon_course(course_id)
            if response.parsed_json and response.parsed_json.get("jargon_course_id"):
                st.success("Jargon course created.")
                st.rerun()
            else:
                for warning in response.warnings:
                    st.warning(warning)

    st.markdown("---")
    d1, d2 = st.columns([1, 1])
    with d1:
        if st.button("Delete Course", key=f"delete_req_{course_id}", use_container_width=True):
            st.session_state["confirm_delete_course"] = course_id
    with d2:
        if st.session_state.get("confirm_delete_course") == course_id:
            if st.button("Confirm Delete", key=f"delete_yes_{course_id}", use_container_width=True):
                delete_course(course_id)
                play_sfx("error")
                st.rerun()

    study_hours = course_credit_hours(course_id)
    assess_hours = get_assessment_hours(course_id)
    if study_hours > 0 or assess_hours > 0:
        st.markdown("---")
        h1, h2, h3 = st.columns(3)
        with h1:
            st.caption(f"Study hours: {study_hours:.1f}")
        with h2:
            st.caption(f"Assessment hours: {assess_hours:.1f}")
        with h3:
            st.caption(f"Estimated credits: {hours_to_credits(study_hours + assess_hours):.2f}")

    readiness = summary["readiness"]
    if readiness["required_missing"] or readiness["recommended_missing"]:
        st.markdown("---")
        if readiness["required_missing"]:
            st.warning("Required gaps: " + ", ".join(readiness["required_missing"][:6]))
        if readiness["recommended_missing"]:
            st.info("Recommended gaps: " + ", ".join(readiness["recommended_missing"][:6]))

    profile = get_competency_profile(course_id)
    has_data = any(profile[level]["assessments"] > 0 for level in BLOOMS_LEVELS)
    if has_data:
        st.markdown("---")
        st.markdown("**Competency Profile (Bloom's Taxonomy)**")
        for level in BLOOMS_LEVELS:
            d = profile[level]
            pct = d["pct"]
            bars = 20
            filled = int(pct / 100 * bars)
            bar = "\u2588" * filled + "\u2591" * (bars - filled)
            colour = "#40dc80" if pct >= 70 else "#ffd700" if pct >= 40 else "#e04040"
            st.markdown(
                f"<div style='font-family:monospace;font-size:0.85rem;'>"
                f"<span style='color:#a0a0c0;'>{level:<14}</span> "
                f"<span style='color:{colour};'>[{bar}]</span> "
                f"<span style='color:#b8b8d0;'>{pct:.0f}% ({d['assessments']} assess)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


def _render_upload_panel() -> None:
    """Upload real-world notes or assignments to auto-generate a full course."""
    with st.expander("Upload Notes / Assignments → Generate Course", expanded=False):
        st.markdown(
            "Upload your university lecture notes, study guides, or assignments. "
            "The AI will analyse the material and generate a complete course."
        )
        uploaded = st.file_uploader(
            "Upload file(s)",
            type=["txt", "md", "csv"],
            accept_multiple_files=True,
            key="upload_notes_files",
        )
        _paste = st.text_area(
            "Or paste content directly",
            height=160,
            placeholder="Paste lecture notes, assignment descriptions, syllabus text…",
            key="upload_notes_paste",
        )
        _level = st.selectbox(
            "Academic level", ["undergraduate", "graduate", "introductory"],
            key="upload_level",
        )
        _lpm = st.slider("Lectures per module", 2, 6, 3, key="upload_lpm")

        if st.button("Generate Course from Upload", use_container_width=True,
                      type="primary", key="upload_gen_btn"):
            parts: list[str] = []
            if uploaded:
                for f in uploaded:
                    try:
                        parts.append(f.read().decode("utf-8", errors="replace"))
                    except Exception as exc:
                        st.warning(f"Could not read {f.name}: {exc}")
            if _paste.strip():
                parts.append(_paste.strip())
            if not parts:
                st.warning("Upload a file or paste content first.")
                return
            content = "\n\n---\n\n".join(parts)
            if len(content.split()) < 50:
                st.warning("Please provide at least 50 words of source material.")
                return
            # Truncate to ~12k words to fit context windows safely
            words = content.split()
            if len(words) > 12_000:
                content = " ".join(words[:12_000])
                st.info("Input truncated to ~12,000 words to fit model context.")

            from llm.professor import Professor

            prof = Professor(session_id="upload_to_course")
            topic_summary = content[:3000]
            progress_bar = st.progress(0, text="Starting course generation…")

            def _progress(msg: str) -> None:
                progress_bar.progress(min(95, progress_bar._value + 15 if hasattr(progress_bar, '_value') else 30), text=msg)

            with st.spinner("Analysing uploaded material and generating course…"):
                # First ask LLM to extract a topic summary from the notes
                from llm.providers import simple_complete, cfg_from_settings
                cfg = cfg_from_settings()
                extract_prompt = (
                    "You are a university curriculum designer. "
                    "Given the following student notes/assignments, produce a concise "
                    "comma-separated list of the core topics covered (max 15 topics). "
                    "Output ONLY the comma-separated list, nothing else.\n\n"
                    f"MATERIAL:\n{topic_summary}"
                )
                topics_raw = simple_complete(cfg, extract_prompt)
                if not topics_raw.strip():
                    st.error("Could not extract topics from the uploaded material.")
                    return
                progress_bar.progress(20, text=f"Topics: {topics_raw.strip()[:80]}…")

                resp = prof.chunked_curriculum(
                    topics_raw.strip(), level=_level,
                    lectures_per_module=_lpm,
                    progress_callback=lambda m: progress_bar.progress(
                        min(90, 25 + 60 * (1 / max(1, 5))), text=m),
                )

            progress_bar.progress(100, text="Done!")
            if resp.parsed_json:
                play_sfx("success")
                st.success("Course generated! Importing…")
                from core.database import bulk_import_json
                raw_json = json.dumps(resp.parsed_json, indent=2)
                count, errors = bulk_import_json(raw_json)
                if count:
                    add_xp(count * 15, "Upload-to-course generation", "upload_gen")
                    st.success(f"Imported {count} object(s) from your uploaded notes.")
                for e in errors:
                    st.error(e)
                with st.expander("Generated Course JSON"):
                    st.code(raw_json, language="json")
                st.rerun()
            else:
                st.error("Course generation failed. Check LLM settings.")
                for w in resp.warnings:
                    st.warning(w)


def render_build_tab(course_index: list[dict], data_dict_fn) -> None:
    section_divider("Build & Import")
    st.markdown(
        """
**How courses are made in this app (simple flow):**
1. **Generate** in `Professor Ileices` (course JSON draft).
2. **Import** JSON here in `Library`.
3. **Upload** real-world notes / assignments to auto-generate a course.
4. **Improve** with `Decompose` and `Generate Jargon Course`.
5. **Study** in `Lecture Studio` and iterate with AI.
"""
    )

    render_import_panel()
    _render_upload_panel()

    st.markdown("### Course Build Controls")
    options = [f"{item['course']['title']} ({item['course']['id']})" for item in course_index]
    selected_label = st.selectbox("Select root course", options)
    selected = next(item for item in course_index if f"{item['course']['title']} ({item['course']['id']})" == selected_label)
    _render_build_controls(selected["course"], selected["summary"], data_dict_fn)
