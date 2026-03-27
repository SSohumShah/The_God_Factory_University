"""Curriculum alignment and token-chunk planning for built-in courses."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

from llm.benchmark import (
    format_eta, get_tps, load_benchmark, run_benchmark, save_benchmark,
    probe_context_window, save_context_window, load_context_window,
    needs_benchmark, get_last_benchmarked_key, set_last_benchmarked_key,
)
from llm.model_profiles import resolve_audit_profile, estimate_audit_seconds
from llm.token_planner import plan_course_generation, estimate_generation_time
from ui.theme import section_divider


def _iter_curriculum_files(curriculum_root: Path):
    yield from curriculum_root.rglob("*.json")


def _safe_load(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data, None
        return None, "root_not_object"
    except Exception as exc:
        return None, str(exc)


def _audit_course_schema(course: dict) -> dict:
    required_course_keys = ["course_id", "title", "description", "subject_id", "modules"]
    recommended_course_keys = ["continuation_prompt", "benchmark_ids", "tags", "depth_target", "pacing"]
    lecture_required = ["learning_objectives", "core_terms", "video_recipe"]
    lecture_recommended = ["assessment", "coding_lab"]

    missing_required = [key for key in required_course_keys if key not in course]
    missing_recommended = [key for key in recommended_course_keys if key not in course]

    lecture_total = 0
    lecture_missing_required = 0
    lecture_missing_recommended = 0
    scene_total = 0

    for module in course.get("modules", []):
        for lecture in module.get("lectures", []):
            lecture_total += 1
            for key in lecture_required:
                if key not in lecture:
                    lecture_missing_required += 1
            for key in lecture_recommended:
                if key not in lecture:
                    lecture_missing_recommended += 1
            recipe = lecture.get("video_recipe", {})
            scenes = recipe.get("scene_blocks", []) if isinstance(recipe, dict) else []
            scene_total += len(scenes)

    return {
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "lecture_total": lecture_total,
        "lecture_missing_required": lecture_missing_required,
        "lecture_missing_recommended": lecture_missing_recommended,
        "scene_total": scene_total,
    }


def render_alignment_tab(curriculum_root: Path) -> None:
    section_divider("Curriculum Alignment")
    st.markdown(
        "Audit built-in curriculum files against current course capabilities, then estimate "
        "how many generation outputs are needed for small vs large models."
    )

    # ── How to turn placeholders into real courses ────────────────────────────
    st.info(
        "**How to turn built-in curriculum into real courses:**\n\n"
        "1. Built-in JSON files are **templates** with placeholder narration.\n"
        "2. Go to **Lecture Studio**, select a lecture, and click "
        "**Enrich Narration with LLM** — this rewrites each scene's narration "
        "into real educational scripts that actually teach.\n"
        "3. Then click **Render** to produce the video with real narration + AI backgrounds.\n"
        "4. Or use **Batch Render** with the 'Enrich narration' checkbox to do all lectures at once.\n"
        "5. Use the **Batch Enrich** button below to enrich ALL imported lectures in one pass."
    )

    # ── Hardware Benchmark ────────────────────────────────────────────────────
    st.markdown("### Hardware / Model Benchmark")
    st.caption(
        "Run a quick test call to measure real tokens-per-second for your current LLM config. "
        "This calibrates all time estimates. Re-run any time you change the model or provider."
    )

    _bm_provider = st.session_state.get("provider", "openai")
    _bm_model = st.session_state.get("model", "gpt-4o-mini")
    _saved_tps = load_benchmark(_bm_provider, _bm_model)
    _saved_ctx = load_context_window(_bm_provider, _bm_model)

    # Detect provider/model change since last benchmark
    _last_bm_key = get_last_benchmarked_key()
    _cur_key = f"{_bm_provider}/{_bm_model}"
    _model_changed = _last_bm_key and _last_bm_key != _cur_key and not _saved_tps

    bm_col1, bm_col2 = st.columns([2, 1])
    with bm_col1:
        if _model_changed:
            st.warning(
                f"Model/provider changed to **{_cur_key}**. "
                "Run a new benchmark for accurate time estimates."
            )
        elif _saved_tps:
            _ctx_str = f" | context ~{_saved_ctx:,} tokens" if _saved_ctx else ""
            st.success(f"Benchmark: **{_saved_tps} tok/s** for {_bm_provider}/{_bm_model}{_ctx_str}")
        else:
            st.info(f"No benchmark for {_bm_provider}/{_bm_model}. Using model-profile estimate.")
    with bm_col2:
        if st.button("Run Benchmark Now", use_container_width=True):
            from llm.providers import cfg_from_settings as _cfg_fs
            _bm_cfg = _cfg_fs()
            with st.spinner("Benchmarking speed + context window…"):
                _bm_result = run_benchmark(_bm_cfg)
                _ctx_result = probe_context_window(_bm_cfg)
            if _bm_result.get("tokens_per_second"):
                save_benchmark(_bm_provider, _bm_model, _bm_result["tokens_per_second"])
                set_last_benchmarked_key(_bm_provider, _bm_model)
                _ctx_tok = _ctx_result.get("estimated_max_output_tokens")
                if _ctx_tok:
                    save_context_window(_bm_provider, _bm_model, _ctx_tok)
                _ctx_msg = f" | Context window: ~{_ctx_tok:,} tokens" if _ctx_tok else ""
                st.success(
                    f"Benchmark: **{_bm_result['tokens_per_second']} tok/s** "
                    f"(latency {_bm_result['latency_s']}s){_ctx_msg}"
                )
                st.rerun()
            else:
                st.error(f"Benchmark failed: {_bm_result.get('error', 'unknown error')}")

    st.markdown("---")

    # ── Batch LLM Enrichment ─────────────────────────────────────────────────
    st.markdown("### Batch Enrich All Lectures")
    st.caption(
        "Rewrite every imported lecture's narration prompts using the LLM so they "
        "actually teach the subject instead of using placeholder text."
    )

    from core.database import get_all_courses, get_modules, get_lectures, update_lecture_data

    db_courses = get_all_courses()

    if db_courses:
        # ── Time estimate + idle-threshold warning ────────────────────────────
        _total_scene_count = 0
        for _ec in db_courses:
            for _em in get_modules(_ec["id"]):
                for _el in get_lectures(_em["id"]):
                    _eld = json.loads(_el.get("data") or "{}")
                    _total_scene_count += len(_eld.get("video_recipe", {}).get("scene_blocks", []))

        _avg_tokens_per_scene = 200
        _total_tok_est = _total_scene_count * _avg_tokens_per_scene
        _tps = get_tps(_bm_provider, _bm_model)
        _eta = _total_tok_est / max(_tps, 0.5)
        _eta_str = format_eta(_eta)

        idle_hours = st.number_input(
            "Idle threshold (hours) — warn if ETA exceeds this",
            min_value=0.1, max_value=24.0, value=2.0, step=0.5,
            help="If the estimated run time is longer than this, you'll be offered options."
        )

        st.info(
            f"**Estimate:** ~{_total_scene_count} scenes × ~{_avg_tokens_per_scene} tokens "
            f"at {_tps:.0f} tok/s → **~{_eta_str}** total."
        )

        _over_threshold = _eta > idle_hours * 3600
        if _over_threshold:
            st.warning(
                f"This batch will take ~{_eta_str}, which exceeds your {idle_hours}h idle threshold. "
                "Choose how to proceed:"
            )
            _run_mode = st.radio(
                "Enrichment mode",
                ["Enrich ONE course now", "Start full run anyway"],
                horizontal=True,
            )
            if _run_mode == "Enrich ONE course now":
                _one_course_map = {f"{c.get('course_id', c['id'])} — {c['title']}": c for c in db_courses}
                _one_sel = st.selectbox("Pick course to enrich", list(_one_course_map.keys()), key="one_enrich_sel")
                db_courses = [_one_course_map[_one_sel]]
        else:
            _run_mode = "Start full run anyway"

    if db_courses and st.button("Enrich ALL Lecture Narration via LLM", use_container_width=True, type="primary"):
        from llm.providers import simple_complete, cfg_from_settings
        import time as _time

        cfg = cfg_from_settings()
        enrich_status = st.empty()
        enrich_bar = st.progress(0)
        _eta_display = st.empty()

        all_lecs = []
        for c in db_courses:
            for m in get_modules(c["id"]):
                for lec in get_lectures(m["id"]):
                    all_lecs.append((c, m, lec))

        total = len(all_lecs)
        enriched = 0
        errors = 0
        _batch_start = _time.perf_counter()

        for idx, (course, module, lec_row) in enumerate(all_lecs):
            lec_data = json.loads(lec_row.get("data") or "{}")
            scenes = lec_data.get("video_recipe", {}).get("scene_blocks", [])
            if not scenes:
                enrich_bar.progress((idx + 1) / total)
                continue

            # Real-time ETA recalculation
            _elapsed = _time.perf_counter() - _batch_start
            if idx > 0:
                _per_item = _elapsed / idx
                _remaining = _per_item * (total - idx)
                _eta_display.caption(
                    f"Elapsed: {format_eta(_elapsed)} | "
                    f"~{format_eta(_remaining)} remaining | "
                    f"{_per_item:.1f}s/lecture"
                )

            enrich_status.caption(f"[{idx+1}/{total}] {lec_row['title']}...")
            any_changed = False

            for si, scene in enumerate(scenes):
                narr = scene.get("narration_prompt", "")
                # Skip already-enriched narration (>100 words suggests real content)
                if len(narr.split()) > 100:
                    continue
                dur = scene.get("duration_s", 60)
                word_target = int(dur * 2.5)
                prompt = (
                    f"Write a {word_target}-word narration script for an educational video.\n"
                    f"Course: {course['title']}\nLecture: {lec_row['title']}\n"
                    f"Scene {si+1}/{len(scenes)}\nDuration: {dur}s\n"
                    f"Topic context: {narr}\n"
                    f"Learning objectives: {', '.join(lec_data.get('learning_objectives', []))}\n"
                    f"Core terms: {', '.join(lec_data.get('core_terms', []))}\n\n"
                    f"ACTUALLY TEACH the subject. Give examples, define terms, explain step by step. "
                    f"Do NOT use markdown or formatting. Do NOT include praise or compliments. "
                    f"Output ONLY plain narration text."
                )
                try:
                    result = simple_complete(cfg, prompt)
                    if result and len(result.split()) > 20:
                        scene["narration_prompt"] = result.strip()
                        any_changed = True
                except Exception:
                    errors += 1

            if any_changed:
                lec_data["video_recipe"]["scene_blocks"] = scenes
                try:
                    update_lecture_data(lec_row["id"], lec_data)
                    enriched += 1
                except Exception:
                    errors += 1

            enrich_bar.progress((idx + 1) / total)

        enrich_status.empty()
        _eta_display.empty()
        enrich_bar.progress(1.0)
        _total_elapsed = _time.perf_counter() - _batch_start
        st.success(
            f"Enriched {enriched} lectures in {format_eta(_total_elapsed)}. "
            f"{errors} errors. Now render them in Lecture Studio or Batch Render."
        )

    st.markdown("---")

    files = list(_iter_curriculum_files(curriculum_root))
    st.caption(f"Built-in curriculum files found: {len(files)}")

    if st.button("Run Built-in Curriculum Audit", use_container_width=True):
        issues = []
        valid = 0
        lecture_total = 0
        scene_total = 0

        for path in files:
            course, error = _safe_load(path)
            if error:
                issues.append({"file": str(path.relative_to(curriculum_root)), "error": error})
                continue
            valid += 1
            result = _audit_course_schema(course)
            lecture_total += result["lecture_total"]
            scene_total += result["scene_total"]
            if result["missing_required"] or result["lecture_missing_required"]:
                issues.append({
                    "file": str(path.relative_to(curriculum_root)),
                    "missing_required": result["missing_required"],
                    "lecture_missing_required_count": result["lecture_missing_required"],
                    "missing_recommended": result["missing_recommended"],
                    "lecture_missing_recommended_count": result["lecture_missing_recommended"],
                })

        st.metric("Valid JSON course files", valid)
        st.metric("Total lectures", lecture_total)
        st.metric("Total scene blocks", scene_total)

        report = {
            "files_scanned": len(files),
            "valid_files": valid,
            "lecture_total": lecture_total,
            "scene_total": scene_total,
            "issues": issues,
        }
        if issues:
            st.warning(f"Found {len(issues)} files with alignment gaps.")
            st.json(issues[:20])
        else:
            st.success("Built-in curriculum appears aligned with required base fields.")

        st.download_button(
            "Download Alignment Report",
            json.dumps(report, indent=2),
            file_name="curriculum_alignment_report.json",
            mime="application/json",
        )

    st.markdown("---")
    st.markdown("### Generation Plan Preview")
    st.caption(
        "Select a curriculum file and model to see how many LLM outputs "
        "the adaptive token planner would generate."
    )

    if files:
        file_map = {str(f.relative_to(curriculum_root)): f for f in files}
        chosen_file = st.selectbox("Course file", list(file_map.keys()))
        course_data, err = _safe_load(file_map[chosen_file])

        provider = st.session_state.get("provider", "openai")
        model = st.session_state.get("model", "gpt-4o-mini")
        profile = resolve_audit_profile(provider, model)

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Active model", f"{provider} / {model}", disabled=True)
        with c2:
            overhead = st.number_input("Overhead tokens", value=500, step=100)

        if course_data and st.button("Preview Generation Plan", use_container_width=True):
            plan = plan_course_generation(
                course_data,
                max_output_tokens=profile.max_packet_tokens,
                chunk_token_target=profile.chunk_token_target,
                overhead_tokens=int(overhead),
                model_family=profile.family,
            )
            time_est = estimate_generation_time(plan, profile.estimated_tokens_per_second)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total outputs", plan.total_outputs)
            m2.metric("Estimated tokens", f"{time_est['total_tokens']:,}")
            m3.metric("Est. minutes", time_est["estimated_minutes"])
            m4.metric("Usable/call", f"{plan.usable_output_per_call:,}")

            # Dynamic output strategy explanation
            _lec_outs = plan.by_type.get("lecture", 0)
            _total_lecs = sum(
                len(m.get("lectures", [])) for m in course_data.get("modules", [])
            )
            if _total_lecs and _lec_outs > _total_lecs:
                st.info(
                    f"Your model ({profile.family}) produces ~{plan.usable_output_per_call:,} "
                    f"tokens per call. Each lecture needs **{_lec_outs // _total_lecs} output(s)**. "
                    f"A larger model would reduce total outputs."
                )
            else:
                st.success(
                    f"Your model ({profile.family}) can generate each lecture in a single output "
                    f"({plan.usable_output_per_call:,} tok/call)."
                )

            st.dataframe(
                [{"type": k, "outputs": v} for k, v in sorted(plan.by_type.items())],
                use_container_width=True,
            )
        elif err:
            st.error(f"Could not parse selected file: {err}")
    else:
        st.info("No curriculum files found.")

    st.markdown("---")
    st.markdown("### Regenerate Built-in Curriculum")
    st.caption(
        "Run the curriculum regeneration script to upgrade all JSON files "
        "to schema v2.0 with enriched metadata."
    )
    if st.button("Regenerate All Curriculum Files", use_container_width=True):
        script = Path(__file__).resolve().parents[2] / "scripts" / "regenerate_curriculum.py"
        if not script.exists():
            st.error("scripts/regenerate_curriculum.py not found.")
        else:
            with st.spinner("Running regeneration…"):
                result = subprocess.run(
                    [sys.executable, str(script)],
                    capture_output=True, text=True, timeout=120,
                )
            if result.returncode == 0:
                st.success("Curriculum regeneration completed successfully.")
            else:
                st.error("Regeneration failed.")
            if result.stdout:
                st.code(result.stdout[-2000:], language="text")
            if result.stderr:
                st.code(result.stderr[-2000:], language="text")

    # ── Gap Remediation ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Fill Curriculum Gaps")
    st.caption(
        "Use the LLM to generate prerequisite courses or fill identified gaps. "
        "Select a course, and the Professor will create missing prerequisites."
    )

    from core.database import get_all_courses, get_modules

    db_courses = get_all_courses()
    if db_courses:
        gap_course_map = {f"{c.get('course_id', c['id'])} — {c['title']}": c for c in db_courses}
        gap_sel = st.selectbox("Course with gaps", list(gap_course_map.keys()), key="gap_course_sel")
        gap_course = gap_course_map[gap_sel]
        gap_data = json.loads(gap_course.get("data") or "{}")
        prereqs = gap_data.get("recommended_prerequisites", gap_data.get("prerequisites", []))

        if prereqs:
            st.markdown(f"**Listed prerequisites:** {', '.join(prereqs)}")

            # Check which prerequisites exist
            existing_ids = {c.get("course_id", c.get("id", "")) for c in db_courses}
            existing_titles = {c.get("title", "").lower() for c in db_courses}
            missing = [p for p in prereqs if p not in existing_ids and p.lower() not in existing_titles]

            if missing:
                st.warning(f"Missing prerequisites: {', '.join(missing)}")
                if st.button("Generate Missing Prerequisites", use_container_width=True, type="primary"):
                    from llm.professor import Professor
                    from core.database import bulk_import_json

                    gen_status = st.empty()
                    for prereq_name in missing:
                        gen_status.caption(f"Generating prerequisite: {prereq_name}...")
                        try:
                            prof = Professor(session_id="gap-fill")
                            result = prof.chunked_curriculum(
                                f"Prerequisite course: {prereq_name} "
                                f"(needed before taking {gap_course['title']})",
                                level="introductory",
                                lectures_per_module=2,
                            )
                            parsed = result.parsed_json if hasattr(result, "parsed_json") and result.parsed_json else {}
                            if parsed:
                                imported, _ = bulk_import_json(parsed)
                                st.success(f"Generated and imported prerequisite: {prereq_name} ({imported} objects)")
                            else:
                                st.warning(f"Could not generate: {prereq_name}")
                        except Exception as e:
                            st.error(f"Failed to generate {prereq_name}: {e}")
                    gen_status.empty()
            else:
                st.success("All listed prerequisites already exist in the library.")
        else:
            st.info("This course has no listed prerequisites.")

        # Decompose for deeper coverage
        mods = get_modules(gap_course["id"])
        if mods:
            st.markdown("---")
            st.caption(
                f"This course has {len(mods)} modules. You can decompose it into "
                f"sub-courses for deeper coverage of each topic."
            )
            if st.button("Decompose into Sub-Courses", use_container_width=True):
                from llm.professor import Professor
                gen_status = st.empty()
                gen_status.caption("Decomposing...")
                try:
                    prof = Professor(session_id="decompose-gap")
                    cid = gap_course.get("course_id", gap_course.get("id", ""))
                    result = prof.decompose_course(cid)
                    parsed = result.parsed_json if hasattr(result, "parsed_json") and result.parsed_json else {}
                    if parsed and parsed.get("sub_courses_created", 0) > 0:
                        st.success(f"Created {parsed['sub_courses_created']} sub-courses!")
                    else:
                        st.warning("Decomposition produced no sub-courses.")
                        st.json(parsed)
                except Exception as e:
                    st.error(f"Decomposition failed: {e}")
                gen_status.empty()
    else:
        st.info("No courses in the library yet.")
