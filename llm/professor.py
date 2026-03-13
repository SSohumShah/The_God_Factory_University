"""
Professor AI agent: curriculum generation, Socratic dialogue, grading,
content expansion, study guides, quiz generation, and research deep-dives.
The professor operates on a LLMConfig from llm/providers.py.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from llm.providers import LLMConfig, chat, simple_complete, cfg_from_settings
from core.database import append_chat, get_chat, save_llm_generated, unlock_achievement, add_xp, get_setting

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
        messages = self._history()
        return chat(self._cfg(), messages, stream=stream)

    # ─── Public methods ──────────────────────────────────────────────────────

    def ask(self, question: str, stream: bool = False):
        """General Socratic dialogue."""
        result = self._record_and_call(question, stream=stream)
        if not stream:
            append_chat(self.session_id, "assistant", str(result))
        return result

    def stream(self, user_input: str):
        """Yield assistant response chunks for streaming display."""
        gen = self._record_and_call(user_input, stream=True)
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
        result = simple_complete(self._cfg(), prompt)
        save_llm_generated(result, "curriculum")
        add_xp(100, "Generated curriculum", "llm_generate")
        return result

    def generate_quiz(self, lecture_data: dict, num_questions: int = 5) -> str:
        title = lecture_data.get("title", "Lecture")
        terms = lecture_data.get("core_terms", [])
        prompt = f"""Create a {num_questions}-question quiz for the lecture: "{title}"
Core terms: {', '.join(terms)}
Output as JSON: {{"title": "...", "questions": [{{"q": "...", "choices": ["A)...","B)...","C)...","D)..."], "answer": "A", "explanation": "..."}}]}}
Output ONLY valid JSON."""
        result = simple_complete(self._cfg(), prompt)
        save_llm_generated(result, "quiz")
        return result

    def generate_homework(self, lecture_data: dict) -> str:
        title = lecture_data.get("title", "Lecture")
        objectives = lecture_data.get("learning_objectives", [])
        lab = lecture_data.get("coding_lab", {})
        prompt = f"""Design a homework assignment for: "{title}"
Objectives: {', '.join(objectives)}
Coding lab context: {lab.get('task', 'N/A')}
Include: written questions, a coding problem, and a reflection prompt.
Output as JSON: {{"title": "...", "type": "homework", "max_score": 100, "parts": [{{"part": "...", "instructions": "...", "points": 0}}]}}"""
        result = simple_complete(self._cfg(), prompt)
        save_llm_generated(result, "homework")
        return result

    def study_guide(self, lecture_data: dict) -> str:
        prompt = f"""Create a concise study guide for: "{lecture_data.get('title', 'Lecture')}"
Core terms: {', '.join(lecture_data.get('core_terms', []))}
Math focus: {', '.join(lecture_data.get('math_focus', []))}
Format as JSON: {{"title": "...", "key_concepts": [...], "formulas": [...], "practice_problems": [...], "further_reading": [...]}}"""
        result = simple_complete(self._cfg(), prompt)
        save_llm_generated(result, "study_guide")
        return result

    def grade_essay(self, essay_text: str, rubric: str = "") -> str:
        prompt = f"""Grade this student essay and provide structured feedback.
Rubric: {rubric or 'Standard academic rubric: clarity, accuracy, depth, examples, conclusion.'}
Essay:
---
{essay_text}
---
Output JSON: {{"score": 85, "max_score": 100, "grade": "B", "strengths": [...], "improvements": [...], "feedback": "..."}}"""
        result = simple_complete(self._cfg(), prompt)
        return result

    def grade_code(self, code_text: str, task_description: str = "") -> str:
        prompt = f"""Review this student code submission.
Task: {task_description or 'General coding task'}
Code:
```
{code_text}
```
Output JSON: {{"score": 80, "max_score": 100, "grade": "B", "correctness": "...", "style": "...", "improvements": [...], "feedback": "..."}}"""
        result = simple_complete(self._cfg(), prompt)
        return result

    def expand_narration(self, scene: dict, lecture: dict) -> str:
        prompt = f"""Write a full, high-quality 60-second voiceover narration script for:
Lecture: {lecture.get('title', '')}
Scene: {scene.get('block_id', 'A')} - {scene.get('visual_prompt', '')}
Narration hint: {scene.get('narration_prompt', '')}
Key terms: {', '.join(lecture.get('core_terms', [])[:6])}
Write in a clear, engaging professor voice. No stage directions, just the spoken text."""
        return simple_complete(self._cfg(), prompt)

    def suggest_next_topics(self, completed_titles: list[str]) -> str:
        prompt = f"""A student has completed these lectures: {', '.join(completed_titles[-10:])}.
Suggest 5 next topics they should study, explain why each is the logical next step.
Output JSON: {{"suggestions": [{{"topic": "...", "rationale": "...", "difficulty": "...", "estimated_hours": 0}}]}}"""
        return simple_complete(self._cfg(), prompt)

    def research_rabbit_hole(self, term: str) -> str:
        prompt = f"""The student wants to go deep on: "{term}".
Provide an exciting research rabbit hole - cutting-edge papers, historical context, 
open problems, surprising connections to other fields, and hands-on experiments.
Output JSON: {{"term": "{term}", "overview": "...", "history": "...", "open_problems": [...], 
"surprising_connections": [...], "hands_on": [...], "papers": [...]}}"""
        result = simple_complete(self._cfg(), prompt)
        save_llm_generated(result, "rabbit_hole")
        return result

    def enhance_video_prompts(self, lecture_data: dict) -> str:
        title = lecture_data.get("title", "")
        scenes = lecture_data.get("video_recipe", {}).get("scene_blocks", [])
        prompt = f"""Enhance these video generation prompts for: "{title}"
Current scenes: {json.dumps(scenes, indent=2)}
Output enhanced JSON replacing 'visual_prompt' and 'ambiance' in each scene with richer, 
more cinematic and educational descriptions. Preserve all other fields.
Output ONLY valid JSON array of scene_blocks."""
        result = simple_complete(self._cfg(), prompt)
        save_llm_generated(result, "enhanced_prompts")
        return result

    def concept_map(self, lecture_data: dict) -> str:
        prompt = f"""Create a concept map for: "{lecture_data.get('title', '')}"
Terms: {', '.join(lecture_data.get('core_terms', []))}
Output JSON: {{"nodes": [{{"id": "...", "label": "...", "type": "concept|term|principle"}}], 
"edges": [{{"from": "...", "to": "...", "label": "...", "type": "is_a|part_of|leads_to|requires"}}]}}"""
        return simple_complete(self._cfg(), prompt)

    def oral_exam(self, lecture_data: dict, student_answer: str, question: str) -> str:
        prompt = f"""Conduct an oral examination.
Lecture: "{lecture_data.get('title', '')}"
Question asked: {question}
Student's answer: {student_answer}
As a professor, respond with follow-up questions, corrections if needed, and encouragement.
Be Socratic - guide them to deeper understanding."""
        return self._record_and_call(
            f"[ORAL EXAM] Q: {question} | Student: {student_answer}"
        )

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
        return result
