"""Output path tests for canonical nested render layout."""
from __future__ import annotations

from pathlib import Path

from media.output_paths import (
    get_full_video_path,
    get_scene_video_path,
    resolve_full_video_path,
    write_render_metadata,
)


LECTURE = {
    "course_id": "freshman_cs101",
    "course_title": "Computer Science Foundations",
    "module_id": "freshman_cs101_m1",
    "module_title": "Binary and Logic",
    "lecture_id": "freshman_cs101_m1_l1",
    "title": "How Computers Count",
}


class TestOutputPaths:
    def test_full_video_path_is_nested(self, tmp_path: Path):
        out = get_full_video_path(LECTURE, tmp_path)
        assert out == tmp_path / "freshman_cs101" / "freshman_cs101_m1" / "freshman_cs101_m1_l1_full.mp4"

    def test_scene_video_path_is_nested(self, tmp_path: Path):
        out = get_scene_video_path(LECTURE, "B", tmp_path, suffix="_edited")
        assert out == tmp_path / "freshman_cs101" / "freshman_cs101_m1" / "freshman_cs101_m1_l1_scene_B_edited.mp4"

    def test_resolve_falls_back_to_legacy_path(self, tmp_path: Path):
        legacy = tmp_path / "freshman_cs101_m1_l1_full.mp4"
        legacy.write_bytes(b"video")
        resolved = resolve_full_video_path(LECTURE, tmp_path)
        assert resolved == legacy

    def test_metadata_written_beside_nested_output(self, tmp_path: Path):
        nested = get_full_video_path(LECTURE, tmp_path)
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_bytes(b"video")
        metadata_path = write_render_metadata(LECTURE, [nested], tmp_path, chunk_by_scene=False)
        assert metadata_path.parent == nested.parent
        assert metadata_path.exists()