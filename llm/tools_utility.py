"""Utility tool definitions for the agent tool registry."""
from __future__ import annotations

import json

from llm.tool_registry import register


@register(
    name="get_lecture_data",
    description="Get full lecture data including scenes, objectives, and terms.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
        },
        "required": ["lecture_id"],
    },
    category="utility",
)
def get_lecture_data(lecture_id: str) -> dict:
    from core.database import get_lecture

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    data["title"] = lecture.get("title", data.get("title", ""))
    return data
