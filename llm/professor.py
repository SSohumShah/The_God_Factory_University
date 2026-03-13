"""
Professor AI agent: curriculum generation, Socratic dialogue, grading,
content expansion, study guides, quiz generation, and research deep-dives.
The professor operates on a LLMConfig from llm/providers.py.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from llm.providers import LLMConfig, chat, simple_complete, cfg_from_settings, estimate_tokens, PROVIDER_CAPABILITIES
from core.database import append_chat, get_chat, save_llm_generated, unlock_achievement, add_xp, get_setting


@dataclass
class ProfessorResponse:
    """Structured wrapper for all Professor method outputs."""
    raw_text: str
    parsed_json: dict | list | None = None
    warnings: list[str] = field(default_factory=list)
    provider_used: str = ""

    def __str__(self) -> str:
        return self.raw_text

ROOT = Path(__file__).resolve().parent.parent

PROFESSOR_SYSTEM = """You are ARCANA, the AI Professor of Arcane University - a legendary institution where knowledge is power.

Your role encompasses ALL dimensions of academic excellence:
- Teach concepts clearly, building intuition before formalism
- Ask Socratic questions that drive discovery
- Generate well-structured curriculum JSON exactly matching the schema when asked
- Write voiceover narration scripts for lecture videos
- Provide detailed feedback on student work
- Suggest research directions and deeper topics
- Create practice problems with worked solutions
- Assess student understanding through dialogue
- Explain your reasoning fully and transparently

Personality: precise, encouraging, intellectually rigorous, occasionally cryptic in a wise way.
You use academic vocabulary but always ensure clarity. You challenge the student to think.

When generating JSON curriculum, always output ONLY valid JSON that matches this schema:
{
  "course_id": "string",
  "title": "string",
  "description": "string",
  "credits": integer,
  "modules": [
    {
      "module_id": "string",
      "title": "string",
      "lectures": [
        {
          "lecture_id": "string",
          "title": "string",
          "duration_min": integer,
          "learning_objectives": ["string"],
          "core_terms": ["string"],
          "math_focus": ["string"],
          "coding_lab": {"language": "string", "task": "string", "deliverable": "string"},
          "video_recipe": {
            "narrative_arc": ["hook","concept","demo","practice","recap"],
            "scene_blocks": [
              {
                "block_id": "A",
                "duration_s": 90,
                "narration_prompt": "string",
                "visual_prompt": "string",
                "ambiance": {"music": "string", "sfx": "string", "color_palette": "string"}
              }
            ]
          }
        }
      ]
    }
  ]
}
"""


class Professor:
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._query_count = 0

    def _cfg(self) -> LLMConfig:
        cfg = cfg_from_settings()
        cfg.system_prompt = PROFESSOR_SYSTEM
        cfg.temperature = 0.72
        cfg.max_tokens = 4096
        return cfg

    def _history(self) -> list[dict]:
        rows = get_chat(self.session_id, limit=20)
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def _record_and_call(self, user_msg: str, stream: bool = False):
        append_chat(self.session_id, "user", user_msg)
        self._query_count += 1
        if self._query_count >= 10:
            unlock_achievement("professor_query")
        messages = self._truncate_history()
        cfg = self._cfg()
        result = chat(cfg, messages, stream=stream)
        return result, cfg.provider

    def _truncate_history(self) -> list[dict]:
        """Return chat history truncated to fit the provider's context window."""
        messages = self._history()
        cfg = self._cfg()
        caps = PROVIDER_CAPABILITIES.get(cfg.provider, {})
        ctx_window = caps.get("context_window", 4096)
        budget = int(ctx_window * 0.75)  # leave room for response
        # Always keep the system message (injected by chat()), so budget is for history
        total = 0
        kept: list[dict] = []
        for msg in reversed(messages):
            tokens = estimate_tokens(msg["content"])
            if total + tokens > budget:
                break
            kept.append(msg)
            total += tokens
        kept.reverse()
        return kept

    def _safe_parse_json(self, raw: str) -> tuple[dict | list | None, list[str]]:
        """Parse JSON from LLM output with repair attempts; return (parsed, warnings)."""
        warnings: list[str] = []
        repaired = self.repair_json(raw)
        if repaired is None:
            warnings.append("LLM returned invalid JSON that could not be repaired")
            return None, warnings
        try:
            parsed = json.loads(repaired)
        except (json.JSONDecodeError, ValueError):
            warnings.append("JSON repair produced unparseable output")
            return None, warnings
        if repaired != raw.strip():
            warnings.append("JSON was auto-repaired from malformed LLM output")
        return parsed, warnings

    def _wrap(self, raw: str, provider: str = "", expect_json: bool = False) -> ProfessorResponse:
        """Build a ProfessorResponse, optionally parsing JSON."""
        parsed = None
        warnings: list[str] = []
        if expect_json:
            parsed, warnings = self._safe_parse_json(raw)
            if parsed and isinstance(parsed, dict):
                # Field validation: warn on suspiciously empty required fields
                for key in ("title", "course_id"):
                    if key in parsed and not parsed[key]:
                        warnings.append(f"Required field '{key}' is empty")
        return ProfessorResponse(
            raw_text=raw, parsed_json=parsed, warnings=warnings, provider_used=provider
        )

    # ─── JSON helpers ────────────────────────────────────────────────────────

    @staticmethod
    def repair_json(raw: str) -> str | None:
        """Attempt to recover valid JSON from malformed LLM output.

        Tries, in order:
          1. Direct parse
          2. Extract from markdown code fences
          3. Strip trailing commas before } or ]
          4. Balance unclosed brackets/braces
        Returns the repaired JSON string, or None if unrecoverable.
        """

        def _try_parse(text: str):
            try:
                json.loads(text)
                return text
            except (json.JSONDecodeError, ValueError):
                return None

        raw = raw.strip()

        # 1. Direct parse
        result = _try_parse(raw)
        if result:
            return result

        # 2. Extract from markdown code fences
        fence = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
        if fence:
            result = _try_parse(fence.group(1).strip())
            if result:
                return result

        # 3. Strip trailing commas (,} or ,])
        cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
        result = _try_parse(cleaned)
        if result:
            return result

        # Also try on fenced content
        if fence:
            cleaned = re.sub(r",\s*([}\]])", r"\1", fence.group(1).strip())
            result = _try_parse(cleaned)
            if result:
                return result

        # 4. Balance unclosed brackets/braces
        opens = {"[": "]", "{": "}"}
        stack = []
        for ch in cleaned:
            if ch in opens:
                stack.append(opens[ch])
            elif ch in ("]", "}"):
                if stack and stack[-1] == ch:
                    stack.pop()
        if stack:
            balanced = cleaned + "".join(reversed(stack))
            result = _try_parse(balanced)
            if result:
                return result

        return None

    # ─── Public methods ──────────────────────────────────────────────────────

    def ask(self, question: str, stream: bool = False):
        """General Socratic dialogue."""
        result, provider = self._record_and_call(question, stream=stream)
        if not stream:
            append_chat(self.session_id, "assistant", str(result))
            return self._wrap(str(result), provider)
        return result

    def stream(self, user_input: str):
        """Yield assistant response chunks for streaming display."""
        gen, _provider = self._record_and_call(user_input, stream=True)
        full = ""
        try:
            for chunk in gen:
                full += chunk
                yield chunk
        except TypeError:
            # Fell back to non-streaming string
            full = str(gen)
            yield full
        append_chat(self.session_id, "assistant", full)

    def generate_curriculum(self, topics: str, level: str = "undergraduate", lectures_per_module: int = 3) -> str:
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

    def generate_quiz(self, lecture_data: dict, num_questions: int = 5) -> str:
        title = lecture_data.get("title", "Lecture")
        terms = lecture_data.get("core_terms", [])
        prompt = f"""Create a {num_questions}-question quiz for the lecture: "{title}"
Core terms: {', '.join(terms)}
Output as JSON: {{"title": "...", "questions": [{{"q": "...", "choices": ["A)...","B)...","C)...","D)..."], "answer": "A", "explanation": "..."}}]}}
Output ONLY valid JSON."""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "quiz")
        return self._wrap(result, cfg.provider, expect_json=True)

    def generate_homework(self, lecture_data: dict) -> str:
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

    def study_guide(self, lecture_data: dict) -> str:
        prompt = f"""Create a concise study guide for: "{lecture_data.get('title', 'Lecture')}"
Core terms: {', '.join(lecture_data.get('core_terms', []))}
Math focus: {', '.join(lecture_data.get('math_focus', []))}
Format as JSON: {{"title": "...", "key_concepts": [...], "formulas": [...], "practice_problems": [...], "further_reading": [...]}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "study_guide")
        return self._wrap(result, cfg.provider, expect_json=True)

    def grade_essay(self, essay_text: str, rubric: str = "") -> str:
        prompt = f"""Grade this student essay and provide structured feedback.
Rubric: {rubric or 'Standard academic rubric: clarity, accuracy, depth, examples, conclusion.'}
Essay:
---
{essay_text}
---
Output JSON: {{"score": 85, "max_score": 100, "grade": "B", "strengths": [...], "improvements": [...], "feedback": "..."}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        return self._wrap(result, cfg.provider, expect_json=True)

    def grade_code(self, code_text: str, task_description: str = "") -> str:
        prompt = f"""Review this student code submission.
Task: {task_description or 'General coding task'}
Code:
```
{code_text}
```
Output JSON: {{"score": 80, "max_score": 100, "grade": "B", "correctness": "...", "style": "...", "improvements": [...], "feedback": "..."}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        return self._wrap(result, cfg.provider, expect_json=True)

    def expand_narration(self, scene: dict, lecture: dict) -> str:
        prompt = f"""Write a full, high-quality 60-second voiceover narration script for:
Lecture: {lecture.get('title', '')}
Scene: {scene.get('block_id', 'A')} - {scene.get('visual_prompt', '')}
Narration hint: {scene.get('narration_prompt', '')}
Key terms: {', '.join(lecture.get('core_terms', [])[:6])}
Write in a clear, engaging professor voice. No stage directions, just the spoken text."""
        cfg = self._cfg()
        return self._wrap(simple_complete(cfg, prompt), cfg.provider)

    def suggest_next_topics(self, completed_titles: list[str]) -> str:
        prompt = f"""A student has completed these lectures: {', '.join(completed_titles[-10:])}.
Suggest 5 next topics they should study, explain why each is the logical next step.
Output JSON: {{"suggestions": [{{"topic": "...", "rationale": "...", "difficulty": "...", "estimated_hours": 0}}]}}"""
        cfg = self._cfg()
        return self._wrap(simple_complete(cfg, prompt), cfg.provider, expect_json=True)

    def research_rabbit_hole(self, term: str) -> str:
        prompt = f"""The student wants to go deep on: "{term}".
Provide an exciting research rabbit hole - cutting-edge papers, historical context, 
open problems, surprising connections to other fields, and hands-on experiments.
Output JSON: {{"term": "{term}", "overview": "...", "history": "...", "open_problems": [...], 
"surprising_connections": [...], "hands_on": [...], "papers": [...]}}"""
        cfg = self._cfg()
        result = simple_complete(cfg, prompt)
        save_llm_generated(result, "rabbit_hole")
        return self._wrap(result, cfg.provider, expect_json=True)

    def enhance_video_prompts(self, lecture_data: dict) -> str:
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

    def concept_map(self, lecture_data: dict) -> str:
        prompt = f"""Create a concept map for: "{lecture_data.get('title', '')}"
Terms: {', '.join(lecture_data.get('core_terms', []))}
Output JSON: {{"nodes": [{{"id": "...", "label": "...", "type": "concept|term|principle"}}], 
"edges": [{{"from": "...", "to": "...", "label": "...", "type": "is_a|part_of|leads_to|requires"}}]}}"""
        cfg = self._cfg()
        return self._wrap(simple_complete(cfg, prompt), cfg.provider, expect_json=True)

    def oral_exam(self, lecture_data: dict, student_answer: str, question: str) -> str:
        prompt = f"""Conduct an oral examination.
Lecture: "{lecture_data.get('title', '')}"
Question asked: {question}
Student's answer: {student_answer}
As a professor, respond with follow-up questions, corrections if needed, and encouragement.
Be Socratic - guide them to deeper understanding."""
        result, provider = self._record_and_call(
            f"[ORAL EXAM] Q: {question} | Student: {student_answer}"
        )
        append_chat(self.session_id, "assistant", str(result))
        return self._wrap(str(result), provider)

    def explain_app(self, question: str) -> str:
        """Explain how the app works using internal documentation — no code secrets exposed."""
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
            PROFESSOR_SYSTEM + "\n\n"
            "You are now in APP GUIDE mode. Answer questions about how to use "
            "the Arcane University application. Use the provided documentation "
            "to give accurate, helpful answers. NEVER output source code, "
            "database queries, file system paths, or internal variable names."
        )
        result = simple_complete(cfg, prompt)
        append_chat(self.session_id, "user", f"[APP GUIDE] {question}")
        append_chat(self.session_id, "assistant", str(result))
        return self._wrap(result, cfg.provider)
