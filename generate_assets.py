import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COURSE_FILE = ROOT / "notes.txt"
DATA_DIR = ROOT / "data"


def load_course() -> dict:
    return json.loads(COURSE_FILE.read_text(encoding="utf-8"))


def flatten_lectures(course: dict) -> list[dict]:
    rows = []
    for module in course.get("modules", []):
        for lecture in module.get("lectures", []):
            row = {
                "lecture_id": lecture["lecture_id"],
                "module_id": lecture["module_id"],
                "module_title": module["title"],
                "title": lecture["title"],
                "duration_min": lecture["duration_min"],
                "prerequisites": lecture.get("prerequisites", []),
                "learning_objectives": lecture.get("learning_objectives", []),
                "core_terms": lecture.get("core_terms", []),
                "math_focus": lecture.get("math_focus", []),
                "ai_focus": lecture.get("ai_focus", []),
                "coding_lab": lecture.get("coding_lab", {}),
                "assessment": lecture.get("assessment", {}),
                "video_recipe": lecture.get("video_recipe", {}),
            }
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def build_voiceover_rows(lectures: list[dict]) -> list[dict]:
    rows = []
    for lecture in lectures:
        arc = lecture.get("video_recipe", {}).get("narrative_arc", [])
        for scene in lecture.get("video_recipe", {}).get("scene_blocks", []):
            prompt = scene.get("narration_prompt", "")
            script = (
                f"Lecture {lecture['lecture_id']} - {lecture['title']}. "
                f"Scene {scene.get('block_id', 'X')}. "
                f"Narrative arc: {', '.join(arc)}. "
                f"Speak clearly and confidently. {prompt} "
                f"Key terms: {', '.join(lecture.get('core_terms', [])[:6])}."
            )
            rows.append(
                {
                    "lecture_id": lecture["lecture_id"],
                    "scene_block_id": scene.get("block_id", "X"),
                    "duration_s": scene.get("duration_s", 120),
                    "voice_style": "clear professor, medium pace, precise diction",
                    "script": script,
                }
            )
    return rows


def runway_prompt(scene: dict, lecture: dict) -> str:
    return (
        "Cinematic educational explainer, high legibility overlays, "
        "clean motion graphics, 16:9, 1080p, slow camera drift, "
        f"subject: {lecture['title']}; visual: {scene.get('visual_prompt', '')}; "
        f"palette: {scene.get('ambiance', {}).get('color_palette', 'ink and cyan')}; "
        "avoid clutter, avoid logos, no watermarks"
    )


def pika_prompt(scene: dict, lecture: dict) -> str:
    return (
        "Educational animation shot, smooth transitions, modern infographics, "
        "text-safe composition, medium contrast, procedural style, "
        f"topic {lecture['lecture_id']} {lecture['title']}; "
        f"scene directive: {scene.get('visual_prompt', '')}; "
        "camera: subtle parallax, no jitter"
    )


def comfy_prompt(scene: dict, lecture: dict) -> dict:
    return {
        "positive": (
            "educational motion design, crisp typography, technical diagrams, "
            "soft volumetric lighting, high detail, no brand marks"
        ),
        "negative": "blurry text, logo, watermark, low contrast, oversaturated",
        "metadata": {
            "lecture_id": lecture["lecture_id"],
            "scene_id": scene.get("block_id", "X"),
            "topic": lecture["title"],
            "visual_prompt": scene.get("visual_prompt", ""),
            "duration_s": scene.get("duration_s", 120),
        },
    }


def build_prompt_pack_rows(lectures: list[dict]) -> list[dict]:
    rows = []
    for lecture in lectures:
        scenes = lecture.get("video_recipe", {}).get("scene_blocks", [])
        rows.append(
            {
                "lecture_id": lecture["lecture_id"],
                "title": lecture["title"],
                "runway_prompts": [runway_prompt(s, lecture) for s in scenes],
                "pika_prompts": [pika_prompt(s, lecture) for s in scenes],
                "comfy_prompts": [comfy_prompt(s, lecture) for s in scenes],
            }
        )
    return rows


def main() -> None:
    course = load_course()
    lectures = flatten_lectures(course)

    write_jsonl(DATA_DIR / "lectures.jsonl", lectures)
    write_jsonl(DATA_DIR / "voiceover_scripts.jsonl", build_voiceover_rows(lectures))
    write_jsonl(DATA_DIR / "prompt_packs.jsonl", build_prompt_pack_rows(lectures))

    manifest = {
        "course_id": course.get("course_id"),
        "total_lectures": len(lectures),
        "files": [
            "data/lectures.jsonl",
            "data/voiceover_scripts.jsonl",
            "data/prompt_packs.jsonl",
        ],
    }
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
