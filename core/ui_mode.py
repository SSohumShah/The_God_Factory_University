"""UI mode helpers for route ownership across student, builder, and operator surfaces."""
from __future__ import annotations

import streamlit as st

from core.database import get_setting, set_setting


MODE_LABELS = {
    "student": "Student",
    "builder": "Builder",
    "operator": "Operator",
}


def get_ui_mode() -> str:
    """Return current UI mode with session-first resolution and safe fallback."""
    mode = st.session_state.get("ui_mode")
    if mode not in MODE_LABELS:
        mode = get_setting("ui_mode", "student")
    if mode not in MODE_LABELS:
        mode = "student"
    st.session_state["ui_mode"] = mode
    return mode


def set_ui_mode(mode: str) -> str:
    """Persist UI mode into session and settings storage."""
    selected = mode if mode in MODE_LABELS else "student"
    st.session_state["ui_mode"] = selected
    set_setting("ui_mode", selected)
    return selected


def require_ui_mode(allowed_modes: tuple[str, ...], area_name: str) -> None:
    """Gate a page to preferred modes with guided student override support."""
    current = get_ui_mode()
    if current in allowed_modes:
        return

    access_key = f"guided_access::{area_name}"
    if st.session_state.get(access_key):
        return

    allowed_labels = [MODE_LABELS.get(mode, mode.title()) for mode in allowed_modes]

    if current == "student":
        st.warning(
            f"`{area_name}` is an advanced engine surface. It is still available in Student mode with guided access."
        )
        st.caption("Recommended modes: " + ", ".join(allowed_labels))
        st.markdown(
            "Use this when you need deeper control (course imports, automation, rendering, diagnostics, or prototype tools)."
        )
        if st.button(f"Open Guided Access: {area_name}"):
            st.session_state[access_key] = True
            st.rerun()
        st.stop()

    st.error(
        f"`{area_name}` is currently configured for {', '.join(allowed_labels)} mode."
    )
    st.caption("Switch mode to continue.")
    target_mode = allowed_modes[0] if allowed_modes else "student"
    if st.button(f"Switch to {MODE_LABELS.get(target_mode, target_mode.title())} Mode"):
        set_ui_mode(target_mode)
        st.rerun()
    st.stop()
