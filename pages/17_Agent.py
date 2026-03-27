"""
Agent Dashboard — Configure, launch, and monitor the autonomous agent.
"""

import json
import sys
import time
import threading
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import get_setting
from core.ui_mode import require_ui_mode
from ui.theme import inject_theme, gf_header, section_divider, help_button
from llm.agent import (
    create_job, list_jobs, load_job, delete_job, run_agent, save_job,
    AgentMode, ReviewMode, AgentJob,
)
from llm.tools import list_tools

inject_theme()
require_ui_mode(("builder", "operator"), "Agent Dashboard")
gf_header("Agent Dashboard", "Autonomous task execution engine")
help_button("agent-dashboard")

# ─── Session state init ──────────────────────────────────────────────────────
if "agent_running" not in st.session_state:
    st.session_state.agent_running = False
if "agent_current_job_id" not in st.session_state:
    st.session_state.agent_current_job_id = None
if "agent_stop_flag" not in st.session_state:
    st.session_state.agent_stop_flag = False
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []

# ─── Sidebar: Configuration ──────────────────────────────────────────────────
with st.sidebar:
    section_divider("Agent Config")

    agent_mode = st.selectbox(
        "Execution Mode",
        ["bounded", "unlimited"],
        help="Bounded: stops after N steps. Unlimited: runs until complete.",
    )
    max_steps = st.slider("Max Steps (bounded)", 5, 200, 20, disabled=(agent_mode == "unlimited"))
    review_mode = st.selectbox(
        "Review Mode",
        ["auto", "review"],
        help="Auto: commits immediately. Review: queues drafts for approval.",
    )
    rate_limit = st.slider("Rate Limit (seconds)", 0.0, 10.0, 1.0, 0.5)

    # Tool category selection
    st.markdown("**Tool Categories**")
    all_cat = sorted(set(t.category for t in list_tools()))
    selected_cats = []
    for cat in all_cat:
        if st.checkbox(cat.title(), value=True, key=f"cat_{cat}"):
            selected_cats.append(cat)

    provider = get_setting("llm_provider", "ollama")
    model = get_setting("llm_model", "llama3")
    st.caption(f"Provider: {provider} | Model: {model}")


# ─── New Task ─────────────────────────────────────────────────────────────────
section_divider("New Task")

task_input = st.text_area(
    "Task Description",
    placeholder="e.g. Create a full 10-module course on Quantum Computing with quizzes and assignments.",
    height=100,
)

col_start, col_stop = st.columns(2)

with col_start:
    if st.button("[>] Launch Agent", disabled=st.session_state.agent_running, use_container_width=True):
        if not task_input.strip():
            st.warning("Enter a task description first.")
        elif not selected_cats:
            st.warning("Select at least one tool category.")
        else:
            job = create_job(
                task=task_input.strip(),
                mode=agent_mode,
                max_steps=max_steps,
                review=review_mode,
                categories=selected_cats,
            )
            job.config.rate_limit_delay = rate_limit
            save_job(job)
            st.session_state.agent_current_job_id = job.job_id
            st.session_state.agent_stop_flag = False
            st.session_state.agent_running = True
            st.session_state.agent_log = []
            st.rerun()

with col_stop:
    if st.button("[X] Stop Agent", disabled=not st.session_state.agent_running, use_container_width=True):
        st.session_state.agent_stop_flag = True
        st.session_state.agent_running = False
        st.info("Stop signal sent — agent will halt after the current step.")


# ─── Active job execution ────────────────────────────────────────────────────
if st.session_state.agent_running and st.session_state.agent_current_job_id:
    job = load_job(st.session_state.agent_current_job_id)
    if job and job.status in ("pending", "running", "paused"):
        section_divider("Executing")
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.empty()

        def _progress(j: AgentJob):
            """Called after each agent step."""
            step_count = len(j.steps)
            limit = j.config.max_steps if j.config.mode == AgentMode.BOUNDED else 100
            pct = min(step_count / max(limit, 1), 1.0)
            st.session_state.agent_log = [
                f"Step {s.step_num}: [{s.action}] {s.content[:120]}"
                for s in j.steps[-20:]
            ]

        def _should_stop() -> bool:
            return st.session_state.agent_stop_flag

        status_text.markdown("**Agent running…** Press Stop to halt after the current step.")

        try:
            result_job = run_agent(job, progress_callback=_progress, stop_flag=_should_stop)
            st.session_state.agent_running = False

            if result_job.status == "completed":
                st.success(f"Task completed in {len(result_job.steps)} steps.")
            elif result_job.status == "failed":
                st.error(f"Agent failed: {result_job.error}")
            else:
                st.info(f"Agent stopped — status: {result_job.status}")

        except Exception as e:
            st.session_state.agent_running = False
            st.error(f"Agent crash: {e}")

        # Show final log
        if st.session_state.agent_log:
            with st.expander("Agent Log", expanded=True):
                for line in st.session_state.agent_log:
                    st.text(line)


# ─── Draft Queue (review mode) ───────────────────────────────────────────────
if st.session_state.agent_current_job_id:
    job = load_job(st.session_state.agent_current_job_id)
    if job and job.draft_queue:
        section_divider("Draft Queue — Review Required")
        for i, draft in enumerate(job.draft_queue):
            with st.expander(f"Draft {i+1}: {draft.get('tool', 'unknown')} — {draft.get('description', '')[:80]}"):
                st.json(draft)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("[OK] Approve", key=f"approve_{i}"):
                        # Execute the queued tool call
                        from llm.tools import call_tool
                        result = call_tool(draft["tool"], draft.get("args", {}))
                        job.draft_queue.pop(i)
                        job.steps.append(
                            __import__("llm.agent", fromlist=["AgentStep"]).AgentStep(
                                step_num=len(job.steps) + 1,
                                action="tool_result",
                                content=f"Approved: {draft['tool']}",
                                tool_name=draft["tool"],
                                tool_result=result,
                            )
                        )
                        save_job(job)
                        st.rerun()
                with c2:
                    if st.button("[X] Reject", key=f"reject_{i}"):
                        job.draft_queue.pop(i)
                        save_job(job)
                        st.rerun()


# ─── Job History ──────────────────────────────────────────────────────────────
section_divider("Job History")
help_button("agent-job-history")
jobs = list_jobs()
if not jobs:
    st.info("No agent jobs yet. Launch a task above to get started.")
else:
    for j in jobs:
        status_emoji = {
            "completed": "[OK]",
            "failed": "[!!]",
            "running": "[..]",
            "paused": "[||]",
            "pending": "[~~]",
        }.get(j["status"], "[??]")

        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            task_preview = j.get("task", "")[:80]
            st.markdown(f"{status_emoji} **{j['job_id'][:8]}** — {task_preview}")
        with col2:
            st.caption(f"{j.get('steps', 0)} steps")
        with col3:
            if st.button("[?]", key=f"view_{j['job_id']}", help="View details"):
                st.session_state[f"expand_{j['job_id']}"] = True

        if st.session_state.get(f"expand_{j['job_id']}"):
            full_job = load_job(j["job_id"])
            if full_job:
                with st.expander(f"Job {j['job_id'][:8]} Details", expanded=True):
                    st.markdown(f"**Task:** {full_job.config.task_description}")
                    st.markdown(f"**Mode:** {full_job.config.mode.value} | **Review:** {full_job.config.review_mode.value}")
                    st.markdown(f"**Status:** {full_job.status} | **Steps:** {len(full_job.steps)}")
                    if full_job.error:
                        st.error(full_job.error)

                    # Step log
                    st.markdown("**Step Log:**")
                    for step in full_job.steps[-30:]:
                        icon = {"think": "[T]", "tool_call": "[C]", "tool_result": "[R]", "error": "[!]", "done": "[OK]"}.get(step.action, "-")
                        line = f"{icon} **Step {step.step_num}** [{step.action}]"
                        if step.tool_name:
                            line += f" `{step.tool_name}`"
                        st.markdown(line)
                        st.caption(step.content[:200])

                    # Resume / Delete buttons
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        if full_job.status in ("paused", "failed") and st.button("[>] Resume", key=f"resume_{j['job_id']}"):
                            st.session_state.agent_current_job_id = j["job_id"]
                            st.session_state.agent_running = True
                            st.session_state.agent_stop_flag = False
                            full_job.status = "pending"
                            save_job(full_job)
                            st.rerun()
                    with rc2:
                        if st.button("[DEL] Delete", key=f"del_{j['job_id']}"):
                            delete_job(j["job_id"])
                            st.session_state.pop(f"expand_{j['job_id']}", None)
                            st.rerun()


# ─── Available Tools Reference ────────────────────────────────────────────────
section_divider("Available Tools")
help_button("agent-tools")
with st.expander("Tool Reference"):
    tools = list_tools()
    for cat in sorted(set(t.category for t in tools)):
        st.markdown(f"### {cat.title()}")
        cat_tools = [t for t in tools if t.category == cat]
        for t in cat_tools:
            review_tag = " [LOCKED]" if t.requires_review else ""
            st.markdown(f"- **{t.name}**{review_tag}: {t.description[:100]}")
