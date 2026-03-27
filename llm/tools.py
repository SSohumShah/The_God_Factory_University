"""Public facade for agent tools and tool registry APIs.

This module keeps the historical import contract (`llm.tools`) while the
implementation lives in focused modules:
- `llm/tool_registry.py`
- `llm/tools_course.py`
- `llm/tools_video.py`
- `llm/tools_utility.py`
"""
from __future__ import annotations

from llm.tool_registry import Tool, call_tool, get_schemas, get_tool, list_tools, register

# Import side-effect modules so all tool decorators register at import time.
import llm.tools_course  # noqa: F401
import llm.tools_video  # noqa: F401
import llm.tools_utility  # noqa: F401

__all__ = [
    "Tool",
    "register",
    "get_tool",
    "list_tools",
    "get_schemas",
    "call_tool",
]
