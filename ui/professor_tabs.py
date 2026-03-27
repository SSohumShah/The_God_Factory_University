"""Professor AI tab render helpers."""
from __future__ import annotations

import json
import time

import streamlit as st

from core.chat_store import export_for_llm, label_session, list_sessions, load_session
from core.database import get_course, get_lectures, get_setting, save_setting
from ui.theme import help_button, play_sfx, sanitize_llm_output, section_divider, stat_card


def render_professor_chat_tab(*, get_professor, get_chat_history, save_chat_history,
                              add_xp, log_activity, provider: str, model: str) -> None:
    section_divider("Conversation")
    help_button("professor-chat")

    if "chat_session_id" not in st.session_state:
        st.session_state["chat_session_id"] = "main"

    s1, s2 = st.columns([3, 1])
    with s1:
        session_id = st.text_input(
            "Session",
            value=st.session_state["chat_session_id"],
            key="session_input",
            label_visibility="collapsed",
            placeholder="Session name (e.g. 'main', 'calculus-help')",
        )
        if session_id != st.session_state["chat_session_id"]:
            st.session_state["chat_session_id"] = session_id
            st.rerun()
    with s2:
        new_name = f"chat-{int(time.time())}"
        if st.button("New Chat", use_container_width=True):
            st.session_state["chat_session_id"] = new_name
            st.rerun()

    session_id = st.session_state["chat_session_id"]
    history = get_chat_history(session_id)

    chat_box = st.container()
    with chat_box:
        for msg in history[-40:]:
            with st.chat_message(msg["role"]):
                st.markdown(sanitize_llm_output(msg["content"]))

    user_input = st.chat_input("Ask the Professor anything...")
    if not user_input:
        return

    save_chat_history(session_id, "user", user_input)
    with chat_box:
        with st.chat_message("user"):
            st.markdown(user_input)

    with chat_box:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            try:
                prof = get_professor(session_id=session_id)
                for chunk in prof.stream(user_input):
                    full_response += chunk
                    placeholder.markdown(sanitize_llm_output(full_response) + " \u25cc")
                placeholder.markdown(sanitize_llm_output(full_response))
                save_chat_history(session_id, "assistant", full_response)
                add_xp(5, "Consulted the Professor", "professor_chat")
                log_activity("professor_chat", metadata={"session_id": session_id, "provider": provider, "model": model})
            except Exception as e:
                full_response = f"(Professor offline: {e})"
                placeholder.error(full_response)
    st.rerun()


def render_curriculum_tab(*, get_professor, get_all_courses, get_modules,
                          bulk_import_json, add_xp, unlock_achievement) -> None:
    section_divider("Curriculum Generator")
    help_button("generate-curriculum")

    # ── Student learning preferences (persistent) ─────────────────────────────
    with st.expander("Student Learning Preferences", expanded=False):
        _saved_prefs = get_setting("student_preferences", "")
        _prefs_input = st.text_area(
            "How do you learn best?",
            value=_saved_prefs,
            height=80,
            placeholder=(
                "E.g. 'I prefer concrete examples before theory. "
                "I'm a visual learner. Keep explanations brief and practical.'"
            ),
            key="student_prefs_input",
        )
        if st.button("Save Preferences", key="save_prefs_btn"):
            save_setting("student_preferences", _prefs_input.strip())
            st.success("Preferences saved — will be injected into all course generation prompts.")
        if _saved_prefs:
            st.caption(f"Active: {_saved_prefs[:120]}{'…' if len(_saved_prefs) > 120 else ''}")

    # ── Existing courses context ──────────────────────────────────────────────
    courses = get_all_courses()
    course_map = {}
    if courses:
        for c in courses:
            cid = c.get("course_id", c.get("id", ""))
            course_map[f"{cid} — {c['title']}"] = c

    # ── Tab sub-sections ──────────────────────────────────────────────────────
    gen_mode = st.radio(
        "Action",
        ["Generate New Course", "Decompose Existing Course", "Generate Jargon Course",
         "Full Plan & Generate"],
        horizontal=True,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # GENERATE NEW COURSE
    # ═══════════════════════════════════════════════════════════════════════════
    if gen_mode == "Generate New Course":
        st.markdown(
            "<span style='color:#a0a0c0;font-family:monospace;font-size:0.85rem;'>"
            "Describe a topic. The Professor will generate a full course JSON with modules, "
            "lectures, scene blocks, and narration — then import it to your Library.</span>",
            unsafe_allow_html=True,
        )
        topic = st.text_area(
            "Topics / subject matter", height=120,
            placeholder="Example: Introduction to Quantum Computing — qubits, gates, entanglement, algorithms",
        )
        lectures_per_module = st.slider("Lectures per module", 1, 8, 3)

        # Token target + credit/time estimate
        tok_col1, tok_col2 = st.columns([2, 1])
        with tok_col1:
            token_target = st.select_slider(
                "Course depth (token target)",
                options=[10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 2_000_000],
                value=100_000,
                format_func=lambda v: f"{v:,} tokens",
                help="More tokens = richer, longer course. Affects LLM output depth."
            )
        with tok_col2:
            _credit_est = max(1, int(token_target / 50_000))
            st.metric("Est. Credits", _credit_est)
            try:
                from llm.benchmark import get_tps, format_eta
                _tps = get_tps(
                    st.session_state.get("provider", "openai"),
                    st.session_state.get("model", "gpt-4o-mini"),
                )
                _eta_s = token_target / max(_tps, 0.5)
                st.caption(f"~{format_eta(_eta_s)} to generate")
            except Exception:
                pass

        _student_prefs = get_setting("student_preferences", "")
        _pref_injection = f"\nStudent learning preferences: {_student_prefs}" if _student_prefs else ""

        if st.button("Generate & Auto-Import", use_container_width=True, type="primary"):
            if not topic.strip():
                st.warning("Enter a topic description first.")
            else:
                _full_topic = topic.strip() + _pref_injection
                status = st.empty()
                with st.spinner("Professor is designing the curriculum..."):
                    try:
                        prof = get_professor("curriculum-generator")

                        def _progress(msg):
                            status.caption(f"⏳ {msg}")

                        result = prof.chunked_curriculum(
                            _full_topic, lectures_per_module=lectures_per_module,
                            progress_callback=_progress,
                        )
                        add_xp(50, f"Generated: {topic[:40]}", "curriculum_generated")
                        unlock_achievement("first_curriculum")
                        play_sfx("unlock")

                        parsed = result.parsed_json if hasattr(result, "parsed_json") and result.parsed_json else result
                        if isinstance(parsed, str):
                            parsed = json.loads(parsed)

                        # Auto-import to library
                        imported, errors = bulk_import_json(parsed)
                        if imported:
                            st.success(f"Course generated and imported! ({imported} objects added to Library)")
                        else:
                            st.warning(f"Generated but import had issues: {errors[:3]}")

                        raw_preview = json.dumps(parsed, indent=2)
                        with st.expander("Generated JSON (preview)"):
                            st.code(raw_preview[:8000], language="json")
                        st.download_button(
                            "Download JSON", raw_preview,
                            file_name="generated_course.json", mime="application/json",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Generation failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # DECOMPOSE EXISTING COURSE
    # ═══════════════════════════════════════════════════════════════════════════
    elif gen_mode == "Decompose Existing Course":
        st.markdown(
            "<span style='color:#a0a0c0;font-family:monospace;font-size:0.85rem;'>"
            "Select a course to break into deeper sub-courses. Each module becomes its own "
            "course with expanded lectures. Results appear in Library &gt; Course Map under the parent.</span>",
            unsafe_allow_html=True,
        )
        if not course_map:
            st.info("No courses loaded. Generate or import one first.")
        else:
            selected = st.selectbox("Course to decompose", list(course_map.keys()), key="decompose_sel")
            course = course_map[selected]
            course_id = course.get("course_id", course.get("id", ""))

            mods = get_modules(course["id"])
            st.caption(f"This course has {len(mods)} modules. Decomposition will create sub-courses from each.")

            if st.button("Decompose Now", use_container_width=True, type="primary"):
                status = st.empty()
                with st.spinner("Decomposing course into sub-courses..."):
                    try:
                        prof = get_professor("decompose")

                        def _progress(msg):
                            status.caption(f"⏳ {msg}")

                        result = prof.decompose_course(course_id, progress_callback=_progress)
                        parsed = result.parsed_json if hasattr(result, "parsed_json") and result.parsed_json else {}

                        if parsed and parsed.get("sub_courses_created", 0) > 0:
                            sub_ids = parsed.get("sub_course_ids", [])
                            st.success(
                                f"Created {parsed['sub_courses_created']} sub-courses "
                                f"at depth {parsed.get('depth', '?')}!"
                            )
                            # Show created sub-courses with details
                            st.markdown("**Created sub-courses:**")
                            from core.database import get_course
                            for sid in sub_ids:
                                sc = get_course(sid)
                                if sc:
                                    sc_mods = get_modules(sid)
                                    lec_count = sum(
                                        len(get_lectures(m["id"])) for m in sc_mods
                                    ) if sc_mods else 0
                                    st.markdown(
                                        f"- **{sc['title']}** (`{sid}`) — "
                                        f"{len(sc_mods)} modules, {lec_count} lectures"
                                    )
                                else:
                                    st.markdown(f"- `{sid}`")
                            st.info(
                                f"These sub-courses are linked to parent **{course.get('title', course_id)}**. "
                                f"View them in **Library → Course Map** (nested under the parent) "
                                f"or select them in **Lecture Studio** to render and study."
                            )
                        else:
                            st.warning("Decomposition ran but no sub-courses were created. Check LLM output.")
                            st.json(parsed)
                    except Exception as e:
                        st.error(f"Decomposition failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # GENERATE JARGON COURSE
    # ═══════════════════════════════════════════════════════════════════════════
    elif gen_mode == "Generate Jargon Course":
        st.markdown(
            "<span style='color:#a0a0c0;font-family:monospace;font-size:0.85rem;'>"
            "Extract all technical terms from a course and generate a terminology-focused "
            "sub-course with definitions, usage, and quizzes for each term.</span>",
            unsafe_allow_html=True,
        )
        if not course_map:
            st.info("No courses loaded. Generate or import one first.")
        else:
            selected = st.selectbox("Source course", list(course_map.keys()), key="jargon_sel")
            course = course_map[selected]
            course_id = course.get("course_id", course.get("id", ""))

            if st.button("Generate Jargon Course", use_container_width=True, type="primary"):
                status = st.empty()
                with st.spinner("Extracting terminology and building jargon course..."):
                    try:
                        prof = get_professor("jargon")

                        def _progress(msg):
                            status.caption(f"⏳ {msg}")

                        result = prof.generate_jargon_course(course_id, progress_callback=_progress)
                        parsed = result.parsed_json if hasattr(result, "parsed_json") and result.parsed_json else {}

                        if parsed and parsed.get("jargon_course_id"):
                            jid = parsed["jargon_course_id"]
                            st.success(
                                f"Jargon course created! ID: {jid} "
                                f"({parsed.get('terms_count', '?')} terms)"
                            )
                            sc = get_course(jid)
                            if sc:
                                sc_mods = get_modules(jid)
                                lec_count = sum(
                                    len(get_lectures(m["id"])) for m in sc_mods
                                ) if sc_mods else 0
                                st.markdown(
                                    f"**{sc['title']}** — {len(sc_mods)} modules, "
                                    f"{lec_count} lectures"
                                )
                            st.info(
                                "The jargon course is linked to the parent course. "
                                "Find it in **Library → Course Map** or select it in "
                                "**Lecture Studio** to render and study the terminology."
                            )
                        else:
                            st.warning("Jargon generation ran but no course was created.")
                            st.json(parsed)
                    except Exception as e:
                        st.error(f"Jargon course generation failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # FULL PLAN & GENERATE
    # ═══════════════════════════════════════════════════════════════════════════
    elif gen_mode == "Full Plan & Generate":
        st.markdown(
            "<span style='color:#a0a0c0;font-family:monospace;font-size:0.85rem;'>"
            "Use the adaptive token-budget planner to generate complete content for an "
            "existing course — fills in all narration scripts, assessments, and enrichments.</span>",
            unsafe_allow_html=True,
        )
        if not course_map:
            st.info("No courses loaded. Generate or import one first.")
        else:
            selected = st.selectbox("Course to enrich", list(course_map.keys()), key="plan_gen_sel")
            course = course_map[selected]
            course_data = json.loads(course.get("data") or "{}")
            course_data.setdefault("course_id", course.get("course_id", course.get("id", "")))
            course_data.setdefault("title", course["title"])

            # Re-attach modules/lectures for the planner
            mods = get_modules(course["id"])
            if "modules" not in course_data:
                from core.database import get_lectures
                module_list = []
                for m in mods:
                    lectures = get_lectures(m["id"])
                    lec_list = []
                    for lec in lectures:
                        ld = json.loads(lec.get("data") or "{}")
                        ld.setdefault("lecture_id", lec["id"])
                        ld.setdefault("title", lec["title"])
                        ld.setdefault("duration_min", lec.get("duration_min", 30))
                        lec_list.append(ld)
                    module_list.append({"module_id": m["id"], "title": m["title"], "lectures": lec_list})
                course_data["modules"] = module_list

            st.caption(f"{len(mods)} modules loaded for planning.")

            if st.button("Plan & Generate All Content", use_container_width=True, type="primary"):
                status = st.empty()
                progress_bar = st.progress(0)
                log_area = st.empty()
                logs = []
                with st.spinner("Running adaptive generation plan..."):
                    try:
                        prof = get_professor("plan-generate")

                        def _progress(msg):
                            logs.append(msg)
                            status.caption(f"⏳ {msg}")
                            log_area.code("\n".join(logs[-15:]), language="text")

                        result = prof.plan_and_generate_course(course_data, progress_callback=_progress)
                        parsed = result.parsed_json if hasattr(result, "parsed_json") and result.parsed_json else {}

                        progress_bar.progress(1.0)
                        successes = parsed.get("succeeded", 0)
                        failures = parsed.get("failed", 0)
                        if successes > 0:
                            st.success(f"Generation complete! {successes} outputs succeeded, {failures} failed.")
                        else:
                            st.warning("Generation ran but produced no successful outputs.")
                        st.json(parsed)
                    except Exception as e:
                        st.error(f"Plan & Generate failed: {e}")


def render_grade_tab(*, get_professor, add_xp, log_activity,
                     provider: str, model: str) -> None:
    section_divider("Grade an Essay or Code Submission")
    help_button("grade-work")
    rubric = st.text_input("Grading rubric (optional)", "Accuracy, Depth, Clarity, Examples, Originality")
    work_type = st.radio("Submission type", ["Essay", "Code"], horizontal=True)
    work_text = st.text_area("Paste submission here", height=200)
    st.number_input("Max points", 10, 200, 100)

    if not st.button("Grade with Professor", use_container_width=True):
        return
    if not work_text.strip():
        st.warning("Paste some work to grade.")
        return

    with st.spinner("Professor is reviewing..."):
        try:
            prof = get_professor("grade-work")
            if work_type == "Essay":
                result = prof.grade_essay(work_text, rubric)
            else:
                result = prof.grade_code(work_text, rubric)
            add_xp(10, "Submitted work for grading", "work_graded")
            log_activity("professor_grade", metadata={"work_type": work_type.lower(), "provider": provider, "model": model})
            st.json(result)
        except Exception as e:
            st.error(f"Grading failed: {e}")


def render_quiz_tab(*, get_professor) -> None:
    section_divider("Quiz Generator")
    help_button("create-quiz")
    quiz_topic = st.text_input("Topic / lecture title for quiz", "")
    num_questions = st.slider("Number of questions", 3, 20, 5)
    st.multiselect(
        "Question types",
        ["multiple_choice", "short_answer", "true_false", "fill_blank"],
        default=["multiple_choice"],
    )
    st.select_slider("Difficulty", ["easy", "medium", "hard", "expert"], value="medium")

    if not st.button("Generate Quiz", use_container_width=True):
        return
    if not quiz_topic.strip():
        st.warning("Enter a topic first.")
        return

    with st.spinner("Professor is crafting questions..."):
        try:
            prof = get_professor("quiz-generator")
            response = prof.generate_quiz({"title": quiz_topic, "core_terms": []}, num_questions)
            play_sfx("collect")
            try:
                raw = response.parsed_json if hasattr(response, "parsed_json") and response.parsed_json else json.loads(str(response))
                quiz = raw if isinstance(raw, dict) else {"questions": []}
            except Exception:
                quiz = {"questions": []}
            st.success(f"Quiz ready: {len(quiz.get('questions', []))} questions")
            for idx, question in enumerate(quiz.get("questions", []), 1):
                q_text = question.get("question") or question.get("q", "")
                with st.expander(f"Q{idx}: {q_text[:80]}"):
                    st.markdown(f"**{q_text}**")
                    if question.get("type"):
                        st.write("**Type:**", question.get("type"))
                    if "choices" in question:
                        for choice in question["choices"]:
                            st.write(f"  - {choice}")
                    st.markdown(f"**Answer:** `{question.get('answer', '')}`")
                    if question.get("explanation"):
                        st.info(question["explanation"])
        except Exception as e:
            st.error(f"Quiz generation failed: {e}")


def render_rabbit_hole_tab(*, get_professor, add_xp, log_activity,
                           provider: str, model: str) -> None:
    section_divider("Research Rabbit Hole")
    help_button("research-rabbit-hole")
    st.markdown(
        "<span style='color:#a0a0c0;font-family:monospace;font-size:0.85rem;'>"
        "Enter a keyword or topic. The Professor will reveal its connections, history, "
        "controversies, open problems, and deeper rabbit holes to explore.</span>",
        unsafe_allow_html=True,
    )
    seed_term = st.text_input("Seed keyword or concept", "")
    st.slider("Exploration depth", 1, 5, 2)

    if not st.button("Dive In", use_container_width=True):
        return
    if not seed_term.strip():
        st.warning("Enter a keyword to explore.")
        return

    with st.spinner("Professor is mapping the labyrinth..."):
        try:
            prof = get_professor("rabbit-hole")
            response = prof.research_rabbit_hole(seed_term)
            add_xp(20, f"Explored: {seed_term}", "rabbit_hole")
            log_activity("professor_research", metadata={"term": seed_term, "provider": provider, "model": model})
            play_sfx("xp_gain")
            try:
                raw = response.parsed_json if hasattr(response, "parsed_json") and response.parsed_json else json.loads(str(response))
                result = raw if isinstance(raw, dict) else {"term": seed_term, "overview": str(response)}
            except Exception:
                result = {"term": seed_term, "overview": str(response)}
            st.markdown(f"### {result.get('term', seed_term)}")
            st.write(result.get("overview", ""))
            for key in ("history", "open_problems", "surprising_connections", "hands_on", "papers"):
                items = result.get(key, [])
                if not items:
                    continue
                with st.expander(key.replace("_", " ").title()):
                    if isinstance(items, list):
                        for item in items:
                            st.write(f"  {item}")
                    else:
                        st.write(items)
        except Exception as e:
            st.error(f"Failed: {e}")


def render_audit_tab(*, get_professor, audit_profile, provider: str, model: str,
                     get_all_courses, create_course_audit_job, list_audit_jobs,
                     get_audit_job, get_audit_packets, get_next_pending_packet,
                     mark_audit_job_started, record_audit_packet_review,
                     fail_audit_job, list_remediation_backlog, bulk_import_json,
                     log_activity) -> None:
    section_divider("Chunked Audit Workbench")
    st.markdown(
        "<span style='color:#a0a0c0;font-family:monospace;font-size:0.85rem;'>"
        "Build a packetized evidence queue for a course, then let the Professor grade one packet at a time. "
        "This is designed for local and cloud models that need small, atomic grading passes instead of one giant prompt."
        "</span>",
        unsafe_allow_html=True,
    )

    st.markdown("**Model-specific grading constraints**")
    for note in audit_profile.notes:
        st.markdown(f"- {note}")

    courses = get_all_courses()
    course_options = {f"{course['id']} -- {course['title']}": course["id"] for course in courses}
    selected_course_label = st.selectbox("Course to audit", list(course_options.keys())) if course_options else None
    selected_course_id = course_options[selected_course_label] if selected_course_label else None

    if selected_course_id and st.button("Create Audit Queue", use_container_width=True):
        try:
            job_id = create_course_audit_job(selected_course_id, provider, model, audit_profile.to_dict())
            play_sfx("success")
            st.session_state["active_audit_job_id"] = job_id
            st.success(f"Created audit queue {job_id}")
            st.rerun()
        except Exception as e:
            st.error(f"Could not create audit queue: {e}")

    jobs = list_audit_jobs(limit=20)
    if jobs:
        default_job = st.session_state.get("active_audit_job_id") or jobs[0]["id"]
        job_ids = [job["id"] for job in jobs]
        selected_job_id = st.selectbox(
            "Recent audit jobs",
            job_ids,
            index=job_ids.index(default_job) if default_job in job_ids else 0,
        )
        st.session_state["active_audit_job_id"] = selected_job_id
        job = get_audit_job(selected_job_id)
        packets = get_audit_packets(selected_job_id)
        pending = [packet for packet in packets if packet.get("status") == "pending"]
        remaining_eta = int((job.get("estimated_seconds", 0) or 0) * (len(pending) / max(job.get("total_packets", 1), 1))) if job else 0

        j1, j2, j3, j4 = st.columns(4)
        with j1:
            stat_card("Packets", f"{job.get('processed_packets', 0)}/{job.get('total_packets', 0)}", colour="#00d4ff")
        with j2:
            stat_card("Status", job.get("status", "queued"), colour="#ffd700")
        with j3:
            stat_card("ETA Left", f"{remaining_eta}s", colour="#40dc80")
        with j4:
            stat_card("Passes", str(job.get("total_passes", audit_profile.recommended_passes)), colour="#e04040")

        run1, run3 = st.columns(2)
        with run1:
            run_next = st.button("Grade Next Packet", use_container_width=True)
        with run3:
            run_batch = st.button("Grade 3 Packets", use_container_width=True)

        if run_next or run_batch:
            try:
                mark_audit_job_started(selected_job_id)
                prof = get_professor("audit-workbench")
                packet_limit = 1 if run_next else 3
                processed_now = 0
                progress_bar = st.progress(0)
                for idx in range(packet_limit):
                    packet = get_next_pending_packet(selected_job_id)
                    if not packet:
                        break
                    result = prof.audit_packet(packet, total_passes=job.get("total_passes", audit_profile.recommended_passes))
                    if not result.parsed_json:
                        fail_audit_job(selected_job_id, "; ".join(result.warnings) or "audit packet parse failed")
                        st.error("Audit packet failed to parse. Job marked failed.")
                        break
                    record_audit_packet_review(packet["id"], result.parsed_json)
                    processed_now += 1
                    progress_bar.progress((idx + 1) / packet_limit)
                if processed_now:
                    play_sfx("collect")
                    log_activity("audit_packets_reviewed", metadata={"job_id": selected_job_id, "count": processed_now, "provider": provider, "model": model})
                    st.success(f"Processed {processed_now} packet(s).")
                    st.rerun()
            except Exception as e:
                fail_audit_job(selected_job_id, str(e))
                st.error(f"Audit run failed: {e}")

        for packet in packets:
            status = packet.get("status", "pending")
            score = packet.get("llm_score")
            score_text = f" | score {score:.0f}" if isinstance(score, (int, float)) else ""
            with st.expander(f"[{status}] {packet.get('title', 'Packet')}{score_text}"):
                st.caption(f"{packet.get('packet_kind', 'packet')} | source {packet.get('source_ref', '')} | est. {packet.get('token_estimate', 0)} tok")
                payload = packet.get("payload_json", "")
                if payload:
                    try:
                        st.json(json.loads(payload))
                    except Exception:
                        st.code(payload[:3000], language="json")
                if packet.get("llm_feedback"):
                    st.markdown("**Professor review**")
                    st.write(packet.get("llm_feedback"))
                weaknesses = packet.get("weaknesses_json")
                if weaknesses:
                    try:
                        weakness_list = json.loads(weaknesses)
                    except Exception:
                        weakness_list = []
                    if weakness_list:
                        st.markdown("**Weaknesses**")
                        for weakness in weakness_list:
                            st.markdown(f"- {weakness}")

    backlog = list_remediation_backlog(limit=20)
    if not backlog:
        return

    section_divider("Remediation Backlog")
    for item in backlog[:10]:
        st.markdown(f"- **{item.get('severity', 'medium').upper()}** {item.get('weakness', '')}")

    weakness_options = [item.get("weakness", "") for item in backlog if item.get("weakness")]
    selected_weaknesses = st.multiselect("Weaknesses to convert into extra-credit course", weakness_options)
    if not (selected_weaknesses and st.button("Draft Extra-Credit Course", use_container_width=True)):
        return

    try:
        prof = get_professor("remediation-generator")
        topic = (
            "Create a harsh but fair extra-credit remediation course that directly repairs these weak areas: "
            + "; ".join(selected_weaknesses)
            + ". Keep it rigorous, atomic, and benchmark-oriented."
        )
        result = prof.generate_curriculum(topic, level="remedial", lectures_per_module=2)
        if not result.parsed_json:
            st.error("Could not draft remediation course.")
            return
        st.success("Extra-credit course drafted.")
        st.json(result.parsed_json)
        if st.button("Import Extra-Credit Course", use_container_width=True):
            raw_json = json.dumps(result.parsed_json)
            imported, errors = bulk_import_json(raw_json)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                play_sfx("unlock")
                log_activity("remediation_course_created", metadata={"weakness_count": len(selected_weaknesses)})
                st.success(f"Imported {imported} objects.")
    except Exception as e:
        st.error(f"Remediation course generation failed: {e}")


def render_history_tab() -> None:
    section_divider("Chat History")
    sessions = list_sessions()
    if not sessions:
        st.info("No saved chat sessions yet. Start chatting in the Chat tab.")
        return

    st.markdown(f"**{len(sessions)} saved sessions**")
    for session in sessions[:30]:
        sid = session.get("session_id", "")
        label = session.get("label", sid)
        count = session.get("message_count", 0)
        with st.expander(f"{label}  ({count} messages)"):
            new_label = st.text_input("Label", value=label, key=f"lbl_{sid}")
            if new_label != label:
                label_session(sid, new_label)

            messages = load_session(sid)
            for msg in messages[-30:]:
                role = msg.get("role", "unknown")
                icon = "user" if role == "user" else "assistant"
                with st.chat_message(icon):
                    st.markdown(sanitize_llm_output(msg.get("content", "")[:1000]))

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Load in Chat Tab", key=f"load_{sid}"):
                    st.session_state["chat_session_id"] = sid
                    st.rerun()
            with c2:
                llm_text = export_for_llm(sid)
                st.download_button(
                    "Export for LLM",
                    llm_text,
                    file_name=f"chat_{sid}.txt",
                    mime="text/plain",
                    key=f"exp_{sid}",
                )


def render_app_guide_tab(*, get_professor, add_xp) -> None:
    section_divider("App Guide — Ask About Any Feature")
    st.markdown(
        "<span style='color:#a0a0c0;font-family:monospace;font-size:0.85rem;'>"
        "Ask the Professor how to use any feature of The God Factory University. "
        "The Professor reads the app documentation and explains in depth — "
        "without revealing any code secrets.</span>",
        unsafe_allow_html=True,
    )

    quick_topics = [
        "How do I import a course?",
        "How does grading work?",
        "What LLM providers are available?",
        "How do I render a lecture video?",
        "What are binaural beats?",
        "How does the degree system work?",
        "How do I set up Ollama locally?",
        "What is the XP and level system?",
    ]

    st.markdown("**Quick Questions:**")
    cols = st.columns(2)
    selected_quick = None
    for idx, question in enumerate(quick_topics):
        with cols[idx % 2]:
            if st.button(question, key=f"quick_{idx}", use_container_width=True):
                selected_quick = question

    custom_question = st.text_input("Or ask your own question:", "")
    question = selected_quick or custom_question
    if not (question and (selected_quick or st.button("Ask Professor", use_container_width=True))):
        return

    with st.spinner("Professor is consulting the archives..."):
        try:
            prof = get_professor("app-guide")
            answer = prof.explain_app(question)
            st.markdown("### Answer")
            st.markdown(sanitize_llm_output(answer))
            add_xp(5, "App guide query", "help")
        except Exception as e:
            st.error(f"Failed: {e}")