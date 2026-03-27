"""Professor mixin: decomposition, jargon, verification, and chunked curriculum workflows."""
from __future__ import annotations

import json
import time

from llm.providers import simple_complete
from core.database import (
    add_xp,
    get_course,
    get_course_depth,
    get_modules,
    save_llm_generated,
    upsert_course,
    upsert_lecture,
    upsert_module,
)
from core.course_tree import (
    build_decomposition_prompt,
    build_jargon_prompt,
    build_verification_prompt,
    get_pacing_for_course,
    register_sub_courses,
)


class ProfessorWorkflowMixin:
    """Curriculum and academic workflow operations."""

    def chunked_curriculum(self, topics: str, level: str = "undergraduate", lectures_per_module: int = 3, progress_callback=None):
        """Generate curriculum in chunks: outline -> modules -> lectures."""
        cfg = self._cfg()
        small = self._is_small_context()

        if progress_callback:
            progress_callback("Generating course outline...")
        outline_prompt = f"""Create a course outline for: {topics}
Level: {level}
Output JSON: {{"course_id": "PREFIX-101", "title": "...", "description": "...", "credits": 3, "module_titles": ["Module 1 title", "Module 2 title", ...]}}
Generate {max(2, lectures_per_module)} to 8 module titles. Output ONLY valid JSON."""
        outline_raw = simple_complete(cfg, outline_prompt)
        outline_resp = self._wrap(outline_raw, cfg.provider, expect_json=True)
        if not outline_resp.parsed_json:
            return outline_resp

        outline = outline_resp.parsed_json
        course_id = outline.get("course_id", "COURSE-101")
        modules = []

        module_titles = outline.get("module_titles", outline.get("modules", []))
        if isinstance(module_titles, list) and module_titles:
            if isinstance(module_titles[0], dict):
                module_titles = [item.get("title", f"Module {idx + 1}") for idx, item in enumerate(module_titles)]

        for idx, module_title in enumerate(module_titles):
            if progress_callback:
                progress_callback(f"Generating module {idx + 1}/{len(module_titles)}: {module_title}")
            module_id = f"{course_id}-M{idx + 1}"
            mod_prompt = f"""Generate {lectures_per_module} lectures for module "{module_title}" in course "{outline.get('title', '')}".
Module ID: {module_id}
Output JSON: {{"module_id": "{module_id}", "title": "{module_title}", "lectures": [
  {{"lecture_id": "{module_id}-L1", "title": "...", "duration_min": 60, "learning_objectives": ["..."], "core_terms": ["..."],
    "video_recipe": {{"scene_blocks": [{{"block_id": "A", "duration_s": 90, "narration_prompt": "...", "visual_prompt": "..."}}]}}
  }}
]}}
Output ONLY valid JSON."""
            mod_raw = simple_complete(cfg, mod_prompt)
            mod_resp = self._wrap(mod_raw, cfg.provider, expect_json=True)
            if mod_resp.parsed_json:
                modules.append(mod_resp.parsed_json)
            else:
                modules.append({"module_id": module_id, "title": module_title, "lectures": []})
            if small:
                time.sleep(0.5)

        full_course = {
            "course_id": course_id,
            "title": outline.get("title", topics[:60]),
            "description": outline.get("description", ""),
            "credits": outline.get("credits", 3),
            "modules": modules,
        }
        raw_json = json.dumps(full_course, indent=2)
        save_llm_generated(raw_json, "curriculum")
        add_xp(100, "Generated curriculum (chunked)", "llm_generate")

        if progress_callback:
            progress_callback("Course generation complete!")

        return self._wrap(raw_json, cfg.provider, expect_json=True)

    def decompose_course(self, course_id: str, depth: int | None = None, pacing: str | None = None, progress_callback=None):
        """Decompose a course into sub-courses based on its modules."""
        from core.database import tx

        course = get_course(course_id)
        if not course:
            return self._wrap("", expect_json=False, provider="")

        modules = get_modules(course_id)
        if not modules:
            return self._wrap("", expect_json=False, provider="")

        current_depth = get_course_depth(course_id)
        target_depth = depth if depth is not None else current_depth + 1
        effective_pacing = pacing or get_pacing_for_course(course_id, tx)

        depth_target = course.get("depth_target") or 0
        if depth_target and target_depth > depth_target:
            return self._wrap(
                "",
                provider="",
                expect_json=False,
            )

        if progress_callback:
            progress_callback(f"Decomposing {course['title']} to depth {target_depth}...")

        prompt = build_decomposition_prompt(course, modules, target_depth, effective_pacing)

        cfg = self._cfg()
        cfg.max_tokens = 8192
        raw = simple_complete(cfg, prompt)
        resp = self._wrap(raw, cfg.provider, expect_json=True)

        if not resp.parsed_json:
            return resp

        parsed = resp.parsed_json
        sub_courses = parsed if isinstance(parsed, list) else [parsed]

        if progress_callback:
            progress_callback(f"Registering {len(sub_courses)} sub-courses...")

        created_ids = register_sub_courses(
            parent_id=course_id,
            sub_courses=sub_courses,
            depth=target_depth,
            pacing=effective_pacing,
            tx_func=tx,
            upsert_course_func=upsert_course,
            upsert_module_func=upsert_module,
            upsert_lecture_func=upsert_lecture,
        )

        save_llm_generated(raw, "decomposition")
        add_xp(150, f"Decomposed {course['title']}", "decompose")

        result = {
            "parent_course_id": course_id,
            "depth": target_depth,
            "pacing": effective_pacing,
            "sub_courses_created": len(created_ids),
            "sub_course_ids": created_ids,
        }

        if progress_callback:
            progress_callback(f"Created {len(created_ids)} sub-courses!")

        return self._wrap(json.dumps(result, indent=2), cfg.provider, expect_json=True)

    def generate_jargon_course(self, course_id: str, progress_callback=None):
        """Generate a jargon/terminology sub-course for a parent course."""
        from core.database import tx

        course = get_course(course_id)
        if not course:
            return self._wrap("", provider="", expect_json=False)

        modules = get_modules(course_id)
        if not modules:
            return self._wrap("", provider="", expect_json=False)

        if progress_callback:
            progress_callback(f"Extracting terminology from {course['title']}...")

        prompt = build_jargon_prompt(course, modules)
        cfg = self._cfg()
        raw = simple_complete(cfg, prompt)
        resp = self._wrap(raw, cfg.provider, expect_json=True)

        if not resp.parsed_json:
            return resp

        jargon_course = resp.parsed_json
        jargon_course["is_jargon_course"] = True
        jargon_course["credits"] = 1

        created_ids = register_sub_courses(
            parent_id=course_id,
            sub_courses=[jargon_course],
            depth=(course.get("depth_level") or 0) + 1,
            pacing=get_pacing_for_course(course_id, tx),
            tx_func=tx,
            upsert_course_func=upsert_course,
            upsert_module_func=upsert_module,
            upsert_lecture_func=upsert_lecture,
        )

        save_llm_generated(raw, "jargon_course")
        add_xp(75, f"Generated jargon course for {course['title']}", "jargon_gen")

        if progress_callback:
            progress_callback("Jargon course created!")

        result = {
            "parent_course_id": course_id,
            "jargon_course_id": created_ids[0] if created_ids else None,
            "terms_count": len((jargon_course.get("jargon") or {}).get("terms", [])),
        }

        return self._wrap(json.dumps(result, indent=2), cfg.provider, expect_json=True)

    def generate_verification(self, assignment_id: str):
        """Generate a prove-it verification assignment for AI-assisted work."""
        from core.database import get_lecture, tx

        with tx() as con:
            row = con.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        if not row:
            return self._wrap("", provider="", expect_json=False)

        assignment = dict(row)
        lecture_title = ""
        if assignment.get("lecture_id"):
            lecture = get_lecture(assignment["lecture_id"])
            if lecture:
                lecture_title = lecture.get("title", "")

        prompt = build_verification_prompt(assignment, lecture_title)
        cfg = self._cfg()
        raw = simple_complete(cfg, prompt)
        resp = self._wrap(raw, cfg.provider, expect_json=True)

        if resp.parsed_json:
            save_llm_generated(raw, "verification_assignment")

        return resp

    # ── Plan-aware generation (Phase 3) ──────────────────────────────────────

    def plan_and_generate_course(self, course: dict, progress_callback=None):
        """Generate full course content using adaptive token-budget planner.

        Uses token_planner to compute exact outputs needed, then feeds them
        through generation_queue for sequential execution with retry.
        """
        from llm.model_profiles import resolve_audit_profile, estimate_audit_seconds
        from llm.token_planner import plan_course_generation, estimate_generation_time
        from llm.generation_queue import GenerationQueue

        cfg = self._cfg()
        profile = resolve_audit_profile(cfg.provider, cfg.model)

        plan = plan_course_generation(
            course=course,
            max_output_tokens=profile.max_packet_tokens,
            chunk_token_target=profile.chunk_token_target,
            overhead_tokens=500,
            model_family=profile.family,
        )

        if progress_callback:
            est = estimate_generation_time(plan, profile.estimated_tokens_per_second)
            progress_callback(
                f"Plan: {est['total_outputs']} outputs, "
                f"~{est['estimated_minutes']} min. Starting generation..."
            )

        def llm_call(task_type: str, prompt: str) -> str:
            return simple_complete(cfg, prompt)

        queue = GenerationQueue(plan=plan, llm_call=llm_call)

        def queue_progress(p):
            if progress_callback:
                progress_callback(f"[{p.completed}/{p.total}] {p.current_task}")

        results = queue.execute(progress_callback=queue_progress)

        save_llm_generated(
            json.dumps(queue.summary(), indent=2),
            "plan_generation",
        )
        add_xp(200, f"Plan-generated {course.get('title', '?')}", "plan_gen")

        if progress_callback:
            progress_callback(
                f"Done! {queue.success_count} succeeded, {queue.failure_count} failed."
            )

        return self._wrap(
            json.dumps(queue.summary(), indent=2),
            cfg.provider,
            expect_json=True,
        )
