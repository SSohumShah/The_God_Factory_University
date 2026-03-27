"""Professor mixin: tutoring, grading, quiz, and content generation flows."""
from __future__ import annotations

import json
import time

from llm.model_profiles import build_audit_prompt_constraints, resolve_audit_profile
from llm.providers import PROVIDER_CAPABILITIES, simple_complete
from core.database import add_remediation_item, add_xp, append_chat, save_llm_generated


class ProfessorContentMixin:
    """Interactive teaching and grading behavior."""

    def generate_curriculum(self, topics: str, level: str = "undergraduate", lectures_per_module: int = 3):
        prompt = f"""Generate a complete course curriculum JSON for:
Topics: {topics}
Level: {level}
Lectures per module: {lectures_per_module}

Output ONLY a valid JSON object matching the schema. No markdown, no explanation before or after. Just the JSON."""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "curriculum")
        add_xp(100, "Generated curriculum", "llm_generate")
        return self._wrap(result, cfg.provider, expect_json=True)

    def generate_quiz(self, lecture_data: dict, num_questions: int = 5):
        title = lecture_data.get("title", "Lecture")
        terms = lecture_data.get("core_terms", [])
        prompt = f"""Create a {num_questions}-question quiz for the lecture: "{title}"
Core terms: {', '.join(terms)}
Output as JSON: {{"title": "...", "questions": [{{"question": "What is...?", "choices": ["A) ...","B) ...","C) ...","D) ..."], "answer": "A", "explanation": "..."}}]}}
IMPORTANT: Each question object MUST have a "question" key with the full question text.
Output ONLY valid JSON."""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "quiz")
        return self._wrap(result, cfg.provider, expect_json=True)

    def generate_homework(self, lecture_data: dict):
        title = lecture_data.get("title", "Lecture")
        objectives = lecture_data.get("learning_objectives", [])
        lab = lecture_data.get("coding_lab", {})
        prompt = f"""Design a homework assignment for: "{title}"
Objectives: {', '.join(objectives)}
Coding lab context: {lab.get('task', 'N/A')}
Include: written questions, a coding problem, and a reflection prompt.
Output as JSON: {{"title": "...", "type": "homework", "max_score": 100, "parts": [{{"part": "...", "instructions": "...", "points": 0}}]}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "homework")
        return self._wrap(result, cfg.provider, expect_json=True)

    def study_guide(self, lecture_data: dict):
        prompt = f"""Create a concise study guide for: "{lecture_data.get('title', 'Lecture')}"
Core terms: {', '.join(lecture_data.get('core_terms', []))}
Math focus: {', '.join(lecture_data.get('math_focus', []))}
Format as JSON: {{"title": "...", "key_concepts": [...], "formulas": [...], "practice_problems": [...], "further_reading": [...]}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "study_guide")
        return self._wrap(result, cfg.provider, expect_json=True)

    def grade_essay(self, essay_text: str, rubric: str = ""):
        prompt = f"""Grade this student essay and provide structured feedback.
Rubric: {rubric or 'Standard academic rubric: clarity, accuracy, depth, examples, conclusion.'}
Essay:
---
{essay_text}
---
{build_audit_prompt_constraints(self._cfg().provider, self._cfg().model)}
Output JSON: {{"score": 85, "max_score": 100, "grade": "B", "strengths": [...], "improvements": [...], "feedback": "..."}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        return self._wrap(result, cfg.provider, expect_json=True)

    def grade_code(self, code_text: str, task_description: str = ""):
        prompt = f"""Review this student code submission.
Task: {task_description or 'General coding task'}
Code:
```
{code_text}
```
{build_audit_prompt_constraints(self._cfg().provider, self._cfg().model)}
Output JSON: {{"score": 80, "max_score": 100, "grade": "B", "correctness": "...", "style": "...", "improvements": [...], "feedback": "..."}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        return self._wrap(result, cfg.provider, expect_json=True)

    def audit_packet(self, packet: dict, total_passes: int | None = None):
        cfg = self._cfg()
        profile = resolve_audit_profile(cfg.provider, cfg.model)
        passes = total_passes if total_passes is not None else profile.recommended_passes
        payload = packet.get("payload_json") or json.dumps(packet.get("payload", {}), ensure_ascii=True)
        prompt = f"""You are grading one atomic audit packet for university credit review.

Packet kind: {packet.get('packet_kind', 'unknown')}
Packet title: {packet.get('title', '')}
Source reference: {packet.get('source_ref', '')}
Required passes: {passes}

{build_audit_prompt_constraints(cfg.provider, cfg.model)}

Academic grading rules:
- Never grant course completion from this packet unless the evidence here proves it.
- If evidence is partial, say insufficient.
- Score harshly. B or below means real weakness.
- Every weakness must be concrete enough to support a remediation course later.

Evidence packet JSON:
{payload}

Output ONLY valid JSON with this exact shape:
{{
  "score": 0,
  "verdict": "pass|borderline|fail|insufficient",
  "confidence": 0.0,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "feedback": "...",
  "credit_recommendation": "grant_none|grant_partial|grant_component",
  "completion_recommendation": "no|not_yet|yes"
}}"""
        result = simple_complete(cfg, prompt)
        wrapped = self._wrap(result, cfg.provider, expect_json=True)
        if wrapped.parsed_json and isinstance(wrapped.parsed_json, dict):
            wrapped.parsed_json.setdefault("reviewer_model", f"{cfg.provider}/{cfg.model}")
            wrapped.parsed_json.setdefault("review_passes", passes)
            score = wrapped.parsed_json.get("score")
            weaknesses = wrapped.parsed_json.get("weaknesses", [])
            if isinstance(score, (int, float)) and score < 90 and weaknesses:
                for weakness in weaknesses[:5]:
                    add_remediation_item(
                        source_type="audit_packet",
                        source_id=str(packet.get("id", "")),
                        course_id=str(packet.get("source_ref", "")),
                        weakness=str(weakness),
                        severity="high" if score < 80 else "medium",
                        suggested_title=f"Remediation: {packet.get('title', 'Weak area')}",
                        data={
                            "packet_kind": packet.get("packet_kind", "unknown"),
                            "packet_title": packet.get("title", ""),
                            "score": score,
                            "provider": cfg.provider,
                            "model": cfg.model,
                        },
                    )
        return wrapped

    def expand_narration(self, scene: dict, lecture: dict):
        prompt = f"""Write a full, high-quality 60-second voiceover narration script for:
Lecture: {lecture.get('title', '')}
Scene: {scene.get('block_id', 'A')} - {scene.get('visual_prompt', '')}
Narration hint: {scene.get('narration_prompt', '')}
Key terms: {', '.join(lecture.get('core_terms', [])[:6])}
Write in a clear, engaging professor voice. No stage directions, just the spoken text."""
        cfg = self._cfg()
        return self._wrap(simple_complete(cfg, prompt), cfg.provider)

    def suggest_next_topics(self, completed_titles: list[str]):
        prompt = f"""A student has completed these lectures: {', '.join(completed_titles[-10:])}.
Suggest 5 next topics they should study, explain why each is the logical next step.
Output JSON: {{"suggestions": [{{"topic": "...", "rationale": "...", "difficulty": "...", "estimated_hours": 0}}]}}"""
        cfg = self._cfg()
        return self._wrap(simple_complete(cfg, prompt), cfg.provider, expect_json=True)

    def research_rabbit_hole(self, term: str):
        prompt = f"""The student wants to go deep on: "{term}".
Provide an exciting research rabbit hole - cutting-edge papers, historical context,
open problems, surprising connections to other fields, and hands-on experiments.
Output JSON: {{"term": "{term}", "overview": "...", "history": "...", "open_problems": [...],
"surprising_connections": [...], "hands_on": [...], "papers": [...]}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "rabbit_hole")
        return self._wrap(result, cfg.provider, expect_json=True)

    def enhance_video_prompts(self, lecture_data: dict):
        title = lecture_data.get("title", "")
        scenes = lecture_data.get("video_recipe", {}).get("scene_blocks", [])
        prompt = f"""Enhance these video generation prompts for: "{title}"
Current scenes: {json.dumps(scenes, indent=2)}
Output enhanced JSON replacing 'visual_prompt' and 'ambiance' in each scene with richer,
more cinematic and educational descriptions. Preserve all other fields.
Output ONLY valid JSON array of scene_blocks."""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "enhanced_prompts")
        return self._wrap(result, cfg.provider, expect_json=True)

    def concept_map(self, lecture_data: dict):
        prompt = f"""Create a concept map for: "{lecture_data.get('title', '')}"
Terms: {', '.join(lecture_data.get('core_terms', []))}
Output JSON: {{"nodes": [{{"id": "...", "label": "...", "type": "concept|term|principle"}}],
"edges": [{{"from": "...", "to": "...", "label": "...", "type": "is_a|part_of|leads_to|requires"}}]}}"""
        cfg = self._cfg()
        return self._wrap(simple_complete(cfg, prompt), cfg.provider, expect_json=True)

    def oral_exam(self, lecture_data: dict, student_answer: str, question: str):
        prompt = f"""Conduct an oral examination.
Lecture: "{lecture_data.get('title', '')}"
Question asked: {question}
Student's answer: {student_answer}
As a professor, respond with follow-up questions, corrections if needed, and encouragement.
Be Socratic - guide them to deeper understanding."""
        result, provider = self._record_and_call(f"[ORAL EXAM] Q: {question} | Student: {student_answer}")
        append_chat(self.session_id, "assistant", str(result))
        return self._wrap(str(result), provider)

    def explain_app(self, question: str):
        """Explain how the app works using internal documentation."""
        from core.app_docs import explain_for_professor

        docs_context = explain_for_professor(question)
        prompt = (
            f"{docs_context}\n\n"
            f"Student asks: {question}\n\n"
            "Explain clearly how this feature works, step by step. "
            "Be helpful and thorough. Do NOT reveal source code, file paths, "
            "SQL queries, or internal implementation details."
        )
        cfg = self._cfg()
        cfg.system_prompt = (
            "You are now in APP GUIDE mode. Answer questions about how to use "
            "The God Factory University application. Use the provided documentation "
            "to give accurate, helpful answers. Do not output source code, "
            "database queries, file system paths, or internal variable names."
        )
        result = simple_complete(cfg, prompt)
        append_chat(self.session_id, "user", f"[APP GUIDE] {question}")
        append_chat(self.session_id, "assistant", str(result))
        return self._wrap(result, cfg.provider)

    def chunked_quiz(self, lecture_data: dict, num_questions: int = 5, progress_callback=None):
        """Generate quiz one question at a time for small models."""
        cfg = self._cfg()
        title = lecture_data.get("title", "Lecture")
        terms = lecture_data.get("core_terms", [])

        if not self._is_small_context():
            return self.generate_quiz(lecture_data, num_questions)

        questions = []
        for idx in range(num_questions):
            if progress_callback:
                progress_callback(f"Generating question {idx + 1}/{num_questions}")
            exclude = json.dumps([question.get("question", "") for question in questions]) if questions else "[]"
            q_prompt = f"""Write 1 quiz question for "{title}" (terms: {', '.join(terms[:5])}).
Do NOT repeat these questions: {exclude}
Output JSON: {{"question": "What is...?", "choices": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A", "explanation": "..."}}
IMPORTANT: Include the "question" key with the full question text.
Output ONLY valid JSON."""
            raw = simple_complete(cfg, q_prompt)
            resp = self._wrap(raw, cfg.provider, expect_json=True)
            if resp.parsed_json and isinstance(resp.parsed_json, dict):
                questions.append(resp.parsed_json)
            time.sleep(0.3)

        quiz = {"title": f"Quiz: {title}", "questions": questions}
        save_llm_generated(json.dumps(quiz), "quiz")
        return self._wrap(json.dumps(quiz, indent=2), cfg.provider, expect_json=True)

    def chunked_rabbit_hole(self, term: str, progress_callback=None):
        """Research rabbit hole in sections for small models."""
        cfg = self._cfg()

        if not self._is_small_context():
            return self.research_rabbit_hole(term)

        sections = {}
        prompts = [
            ("overview", f'Write a 2-paragraph overview of "{term}". Output ONLY the text.'),
            ("history", f'Write the historical context of "{term}" in 2-3 paragraphs. Output ONLY the text.'),
            ("open_problems", f'List 3 open problems related to "{term}". Output JSON: ["problem 1", "problem 2", "problem 3"]'),
            ("connections", f'List 3 surprising connections between "{term}" and other fields. Output JSON: ["connection 1", "connection 2", "connection 3"]'),
            ("hands_on", f'Suggest 2 hands-on experiments for "{term}". Output JSON: ["experiment 1", "experiment 2"]'),
        ]
        for idx, (key, prompt) in enumerate(prompts):
            if progress_callback:
                progress_callback(f"Researching {key} ({idx + 1}/{len(prompts)})")
            raw = simple_complete(cfg, prompt)
            if key in ("open_problems", "connections", "hands_on"):
                resp = self._wrap(raw, cfg.provider, expect_json=True)
                sections[key] = resp.parsed_json if resp.parsed_json else [raw[:200]]
            else:
                sections[key] = raw
            time.sleep(0.3)

        result = {"term": term, **sections}
        save_llm_generated(json.dumps(result), "rabbit_hole")
        return self._wrap(json.dumps(result, indent=2), cfg.provider, expect_json=True)
