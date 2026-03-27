"""Video-editing tool definitions for the agent tool registry."""
from __future__ import annotations

import json

from llm.tool_registry import register


@register(
    name="list_scenes",
    description="List all scenes for a lecture.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
        },
        "required": ["lecture_id"],
    },
    category="video",
)
def list_scenes(lecture_id: str) -> dict:
    from core.database import get_lecture

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    scenes = data.get("video_recipe", {}).get("scene_blocks", [])
    return {
        "lecture_id": lecture_id,
        "scenes": [
            {
                "block_id": scene.get("block_id"),
                "duration_s": scene.get("duration_s"),
                "narration_prompt": scene.get("narration_prompt", "")[:100],
                "visual_prompt": scene.get("visual_prompt", "")[:100],
            }
            for scene in scenes
        ],
    }


@register(
    name="edit_scene",
    description="Edit a scene's narration, visual prompt, or duration.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
            "block_id": {"type": "string"},
            "narration_prompt": {"type": "string"},
            "visual_prompt": {"type": "string"},
            "duration_s": {"type": "integer"},
        },
        "required": ["lecture_id", "block_id"],
    },
    category="video",
)
def edit_scene(lecture_id: str, block_id: str, narration_prompt: str | None = None,
               visual_prompt: str | None = None, duration_s: int | None = None) -> dict:
    from core.database import get_lecture

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    scenes = data.get("video_recipe", {}).get("scene_blocks", [])
    found = False
    for scene in scenes:
        if scene.get("block_id") == block_id:
            if narration_prompt is not None:
                scene["narration_prompt"] = narration_prompt
            if visual_prompt is not None:
                scene["visual_prompt"] = visual_prompt
            if duration_s is not None:
                scene["duration_s"] = duration_s
            found = True
            break
    if not found:
        return {"error": f"Scene {block_id} not found"}
    _update_lecture_data(lecture_id, data)
    return {"status": "updated", "block_id": block_id}


@register(
    name="add_scene",
    description="Add a new scene to a lecture's video recipe.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
            "block_id": {"type": "string"},
            "narration_prompt": {"type": "string"},
            "visual_prompt": {"type": "string"},
            "duration_s": {"type": "integer"},
            "insert_after": {"type": "string", "description": "block_id to insert after (omit for end)"},
        },
        "required": ["lecture_id", "block_id", "narration_prompt", "visual_prompt", "duration_s"],
    },
    category="video",
)
def add_scene(lecture_id: str, block_id: str, narration_prompt: str,
              visual_prompt: str, duration_s: int, insert_after: str = "") -> dict:
    from core.database import get_lecture

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    recipe = data.setdefault("video_recipe", {})
    scenes = recipe.setdefault("scene_blocks", [])
    new_scene = {
        "block_id": block_id,
        "duration_s": duration_s,
        "narration_prompt": narration_prompt,
        "visual_prompt": visual_prompt,
        "ambiance": {"music": "ambient", "sfx": "gentle", "color_palette": "cyan and dark"},
    }
    if insert_after:
        idx = next((i for i, scene in enumerate(scenes) if scene.get("block_id") == insert_after), -1)
        if idx >= 0:
            scenes.insert(idx + 1, new_scene)
        else:
            scenes.append(new_scene)
    else:
        scenes.append(new_scene)
    _update_lecture_data(lecture_id, data)
    return {"status": "added", "block_id": block_id, "total_scenes": len(scenes)}


@register(
    name="remove_scene",
    description="Remove a scene from a lecture.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
            "block_id": {"type": "string"},
        },
        "required": ["lecture_id", "block_id"],
    },
    category="video",
)
def remove_scene(lecture_id: str, block_id: str) -> dict:
    from core.database import get_lecture

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    scenes = data.get("video_recipe", {}).get("scene_blocks", [])
    original_len = len(scenes)
    scenes = [scene for scene in scenes if scene.get("block_id") != block_id]
    if len(scenes) == original_len:
        return {"error": f"Scene {block_id} not found"}
    data["video_recipe"]["scene_blocks"] = scenes
    _update_lecture_data(lecture_id, data)
    return {"status": "removed", "remaining_scenes": len(scenes)}


@register(
    name="reorder_scenes",
    description="Reorder scenes in a lecture by providing the block_ids in desired order.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
            "scene_order": {"type": "array", "items": {"type": "string"}, "description": "block_ids in desired order"},
        },
        "required": ["lecture_id", "scene_order"],
    },
    category="video",
)
def reorder_scenes(lecture_id: str, scene_order: list[str]) -> dict:
    from core.database import get_lecture

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    scenes_by_id = {scene["block_id"]: scene for scene in data.get("video_recipe", {}).get("scene_blocks", [])}
    reordered = [scenes_by_id[block_id] for block_id in scene_order if block_id in scenes_by_id]
    data.setdefault("video_recipe", {})["scene_blocks"] = reordered
    _update_lecture_data(lecture_id, data)
    return {"status": "reordered", "order": scene_order}


@register(
    name="enhance_narration",
    description="Use LLM to rewrite/improve a scene's narration script.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
            "block_id": {"type": "string"},
            "style": {"type": "string", "description": "Style hint, e.g. 'more engaging', 'simpler'"},
        },
        "required": ["lecture_id", "block_id"],
    },
    category="video",
)
def enhance_narration(lecture_id: str, block_id: str, style: str = "clear and engaging") -> dict:
    from core.database import get_lecture
    from llm.providers import simple_complete, cfg_from_settings

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    scenes = data.get("video_recipe", {}).get("scene_blocks", [])
    scene = next((item for item in scenes if item.get("block_id") == block_id), None)
    if not scene:
        return {"error": f"Scene {block_id} not found"}
    cfg = cfg_from_settings()
    prompt = (
        f"Rewrite this narration script to be {style}.\n"
        f"Original: {scene.get('narration_prompt', '')}\n"
        f"Lecture context: {data.get('title', '')}\n"
        "Output only the rewritten narration text, nothing else."
    )
    result = simple_complete(cfg, prompt)
    if not result.startswith("[LLM ERROR]"):
        scene["narration_prompt"] = result
        _update_lecture_data(lecture_id, data)
        return {"status": "enhanced", "block_id": block_id, "new_narration": result[:200]}
    return {"error": result}


@register(
    name="render_lecture",
    description="Render a lecture to MP4 video.",
    parameters={
        "type": "object",
        "properties": {
            "lecture_id": {"type": "string"},
        },
        "required": ["lecture_id"],
    },
    category="video",
)
def render_lecture_tool(lecture_id: str) -> dict:
    from pathlib import Path

    from core.database import get_lecture
    from media.video_engine import render_lecture as _render

    lecture = get_lecture(lecture_id)
    if not lecture:
        return {"error": f"Lecture {lecture_id} not found"}
    data = json.loads(lecture.get("data") or "{}")
    data.setdefault("lecture_id", lecture_id)
    data.setdefault("title", lecture.get("title", "Lecture"))
    output_dir = Path("exports") / "renders"
    try:
        paths = _render(data, output_dir)
        return {"status": "rendered", "files": [str(path) for path in paths]}
    except Exception as exc:
        return {"error": str(exc)}


def _update_lecture_data(lecture_id: str, data: dict) -> None:
    """Update the data JSON blob for a lecture in the DB."""
    from core.database import tx

    with tx() as con:
        con.execute(
            "UPDATE lectures SET data=? WHERE id=?",
            (json.dumps(data), lecture_id),
        )
