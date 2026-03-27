"""Abstract base for image generation providers."""
from __future__ import annotations

import abc
from pathlib import Path


class ImageProvider(abc.ABC):
    """Interface every image generation provider must implement."""

    name: str = "base"
    daily_limit: int | None = None  # None = unlimited

    @abc.abstractmethod
    def generate_image(self, prompt: str, width: int = 960, height: int = 540) -> Path | None:
        """Generate an image from a text prompt. Returns path or None on failure."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is configured and reachable."""

    def remaining_quota(self) -> int | None:
        """Remaining daily quota. None = unlimited or unknown."""
        return self.daily_limit
