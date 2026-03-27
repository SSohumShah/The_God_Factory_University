"""Backward-compatible shim - all logic moved to media.video subpackage."""
from media.video.encoder import render_lecture, batch_render_all, reorder_and_render

__all__ = ["render_lecture", "batch_render_all", "reorder_and_render"]
