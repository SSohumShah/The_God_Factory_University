"""Professor AI — LLM-powered academic advisor, tutor, and curriculum generator."""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_setting, save_chat_history, get_chat_history, bulk_import_json,
    add_xp, unlock_achievement, get_modules,
    get_student_world_state, create_course_audit_job, list_audit_jobs,
    get_audit_job, get_audit_packets, get_next_pending_packet,
    mark_audit_job_started, record_audit_packet_review, fail_audit_job,
    list_remediation_backlog, get_all_courses, log_activity,
)
from llm.model_profiles import resolve_audit_profile
from ui.professor_tabs import (
    render_app_guide_tab,
    render_audit_tab,
    render_curriculum_tab,
    render_grade_tab,
    render_history_tab,
    render_professor_chat_tab,
    render_quiz_tab,
    render_rabbit_hole_tab,
)
from ui.theme import inject_theme, gf_header, stat_card, help_button

inject_theme()
gf_header("Professor AI", "Ileices — your blunt, brilliant guide at The God Factory.")
help_button("professor-chat")

# ─── Provider status bar ──────────────────────────────────────────────────────
provider = get_setting("llm_provider", "ollama")
model = get_setting("llm_model", "llama3")

status_icon = {
    "ollama": "[LOCAL]",
    "lm_studio": "[LOCAL]",
    "openai": "[API]",
    "github": "[API]",
    "anthropic": "[API]",
    "groq": "[FREE]",
    "mistral": "[API]",
    "together": "[API]",
    "huggingface": "[FREE]",
}.get(provider, "[?]")

st.markdown(
    f"<div style='font-family:monospace;color:#606080;font-size:0.8rem;margin-bottom:8px;'>"
    f"PROFESSOR  {status_icon}  {provider.upper()}  /  {model}  "
    f"— configure in Settings</div>",
    unsafe_allow_html=True,
)
audit_profile = resolve_audit_profile(provider, model)
world_state = get_student_world_state()

top1, top2, top3, top4 = st.columns(4)
with top1:
    stat_card("Active Days", str(world_state.get("active_days", 0)), colour="#00d4ff")
with top2:
    stat_card("Study Hours", f"{world_state.get('study_hours', 0.0):.1f}", colour="#ffd700")
with top3:
    idle_days = world_state.get("idle_days")
    stat_card("Idle Days", f"{idle_days:.2f}" if idle_days is not None else "--", colour="#e04040")
with top4:
    stat_card("Audit Passes", str(audit_profile.recommended_passes), colour="#40dc80")

st.caption(
    f"Model audit profile: {audit_profile.label} | chunk target {audit_profile.chunk_token_target} tok | "
    f"structured output: {audit_profile.structured_output_mode} | hallucination risk: {audit_profile.hallucination_risk}"
)

def get_professor(session_id: str = "main"):
    from llm.professor import Professor
    return Professor(session_id=session_id)

# ─── Action tabs ─────────────────────────────────────────────────────────────
tab_chat, tab_gen, tab_grade, tab_quiz, tab_rabbit, tab_audit, tab_history, tab_guide = st.tabs([
    "Chat",
    "Generate Curriculum",
    "Grade Work",
    "Create Quiz",
    "Research Rabbit Hole",
    "Audit Workbench",
    "Chat History",
    "App Guide",
])

with tab_chat:
    render_professor_chat_tab(
        get_professor=get_professor,
        get_chat_history=get_chat_history,
        save_chat_history=save_chat_history,
        add_xp=add_xp,
        log_activity=log_activity,
        provider=provider,
        model=model,
    )

with tab_gen:
    render_curriculum_tab(
        get_professor=get_professor,
        get_all_courses=get_all_courses,
        get_modules=get_modules,
        bulk_import_json=bulk_import_json,
        add_xp=add_xp,
        unlock_achievement=unlock_achievement,
    )

with tab_grade:
    render_grade_tab(
        get_professor=get_professor,
        add_xp=add_xp,
        log_activity=log_activity,
        provider=provider,
        model=model,
    )

with tab_quiz:
    render_quiz_tab(get_professor=get_professor)

with tab_rabbit:
    render_rabbit_hole_tab(
        get_professor=get_professor,
        add_xp=add_xp,
        log_activity=log_activity,
        provider=provider,
        model=model,
    )

with tab_audit:
    render_audit_tab(
        get_professor=get_professor,
        audit_profile=audit_profile,
        provider=provider,
        model=model,
        get_all_courses=get_all_courses,
        create_course_audit_job=create_course_audit_job,
        list_audit_jobs=list_audit_jobs,
        get_audit_job=get_audit_job,
        get_audit_packets=get_audit_packets,
        get_next_pending_packet=get_next_pending_packet,
        mark_audit_job_started=mark_audit_job_started,
        record_audit_packet_review=record_audit_packet_review,
        fail_audit_job=fail_audit_job,
        list_remediation_backlog=list_remediation_backlog,
        bulk_import_json=bulk_import_json,
        log_activity=log_activity,
    )

with tab_history:
    render_history_tab()

with tab_guide:
    render_app_guide_tab(get_professor=get_professor, add_xp=add_xp)
