"""Base Professor mixin: config, history, parsing, and core dialogue."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from llm.providers import (
    LLMConfig,
    PROVIDER_CAPABILITIES,
    cfg_from_settings,
    chat,
    estimate_tokens,
    simple_complete,
)
from core.database import (
    add_xp,
    append_chat,
    get_academic_progress_summary,
    get_chat,
    get_student_world_state,
    list_remediation_backlog,
    unlock_achievement,
)


@dataclass
class ProfessorResponse:
    """Structured wrapper for all Professor method outputs."""

    raw_text: str
    parsed_json: dict | list | None = None
    warnings: list[str] = field(default_factory=list)
    provider_used: str = ""

    def __str__(self) -> str:
        return self.raw_text


PROFESSOR_SYSTEM = """You are Professor Ileices of The God Factory University.

You are a real-world academic professor. You teach real subjects: computer science, mathematics, physics, biology, chemistry, history, philosophy, economics, engineering, literature, and more.

The God Factory University is an institution where students become extraordinary thinkers through deep study and mastery of real-world academic disciplines. The name reflects the belief that rigorous education transforms people.

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

Personality: blunt, direct, academically harsh, and intellectually rigorous.
You respect the student's time - no fluff, no pleasantries beyond necessity.
You use precise academic vocabulary but always ensure clarity. You challenge the student to think harder.
You do not give away credit emotionally. If the evidence is weak, you say it is weak.
If a student performs below an A standard, identify the weakness precisely and assign extra remediation.

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


class ProfessorBaseMixin:
    """Shared base behavior for the Professor class."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._query_count = 0

    def _cfg(self) -> LLMConfig:
        cfg = cfg_from_settings()
        cfg.system_prompt = PROFESSOR_SYSTEM + "\n\n" + self._student_context_block()
        cfg.temperature = 0.72
        cfg.max_tokens = 4096
        return cfg

    def _student_context_block(self) -> str:
        world = get_student_world_state()
        academic = get_academic_progress_summary()
        backlog = list_remediation_backlog(limit=5)
        weakness_lines = [item.get("weakness", "") for item in backlog[:5] if item.get("weakness")]
        lines = [
            "Current student state:",
            f"- Verified credits: {academic.get('official_credits', 0):.2f}",
            f"- Activity credits: {academic.get('activity_credits', 0):.2f}",
            f"- Verified courses: {academic.get('completed_courses', 0)}",
            f"- Verified assessments: {academic.get('verified_assessments', 0)}",
            f"- Study hours: {world.get('study_hours', 0.0):.1f}",
            f"- Days enrolled: {world.get('days_enrolled', 0)}",
            f"- Active days: {world.get('active_days', 0)}",
        ]
        idle_days = world.get("idle_days")
        if idle_days is not None:
            lines.append(f"- Student idle for about {idle_days:.2f} days")
        if weakness_lines:
            lines.append("- Weakness backlog: " + "; ".join(weakness_lines[:5]))
        return "\n".join(lines)

    def _history(self) -> list[dict]:
        rows = get_chat(self.session_id, limit=20)
        return [{"role": row["role"], "content": row["content"]} for row in rows]

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
        budget = int(ctx_window * 0.75)
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
        """Parse JSON from LLM output with repair attempts."""
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
                for key in ("title", "course_id"):
                    if key in parsed and not parsed[key]:
                        warnings.append(f"Required field '{key}' is empty")
        return ProfessorResponse(
            raw_text=raw,
            parsed_json=parsed,
            warnings=warnings,
            provider_used=provider,
        )

    @staticmethod
    def repair_json(raw: str) -> str | None:
        """Attempt to recover valid JSON from malformed LLM output."""

        def _try_parse(text: str):
            try:
                json.loads(text)
                return text
            except (json.JSONDecodeError, ValueError):
                return None

        raw = raw.strip()

        result = _try_parse(raw)
        if result:
            return result

        fence = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
        if fence:
            result = _try_parse(fence.group(1).strip())
            if result:
                return result

        cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
        result = _try_parse(cleaned)
        if result:
            return result

        if fence:
            cleaned = re.sub(r",\s*([}\]])", r"\1", fence.group(1).strip())
            result = _try_parse(cleaned)
            if result:
                return result

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
            full = str(gen)
            yield full
        append_chat(self.session_id, "assistant", full)

    def _is_small_context(self) -> bool:
        """Check if current provider has a small context window (<=8K)."""
        cfg = self._cfg()
        caps = PROVIDER_CAPABILITIES.get(cfg.provider, {})
        return caps.get("context_window", 4096) <= 8192
