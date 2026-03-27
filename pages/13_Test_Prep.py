"""
Standardized Test Prep — GED / SAT / ACT / GRE practice with timed mode.
"""

import sys
import json
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import add_xp, tx
from core.ui_mode import require_ui_mode
from core import test_prep
from ui.theme import inject_theme, gf_header, section_divider, stat_card, help_button

inject_theme()
require_ui_mode(("operator",), "Test Prep")
gf_header("Test Prep", "Practice standardized tests with adaptive scoring.")
help_button("test-prep")
st.warning("Prototype status: current practice items are placeholder content. Timing and score reports are useful for workflow testing, not real exam benchmarking.")

# ─── Test Selection ───────────────────────────────────────────────────────────
section_divider("Select Test")

tests = test_prep.get_test_names()
sel_test = st.selectbox("Test", tests)
sections = test_prep.get_sections(sel_test)
sel_section = st.selectbox("Section", sections) if sections else None

# ─── Session State ────────────────────────────────────────────────────────────
if "tp_session_id" not in st.session_state:
    st.session_state.tp_session_id = None
    st.session_state.tp_questions = []
    st.session_state.tp_current_q = 0
    st.session_state.tp_answers = []
    st.session_state.tp_finished = False
    st.session_state.tp_start_time = None

NUM_QUESTIONS = 10
TIME_LIMIT_S = 600  # 10 minutes

# ─── Start Test ───────────────────────────────────────────────────────────────
section_divider("Practice Session")

if st.session_state.tp_session_id is None:
    st.info(f"**{sel_test}** — {sel_section or 'All Sections'} | {NUM_QUESTIONS} questions | {TIME_LIMIT_S // 60} min time limit")
    timed = st.checkbox("Enable timer", value=True)

    if st.button("Start Practice", type="primary"):
        sid = test_prep.start_session(sel_test, sel_section or "", tx)
        st.session_state.tp_session_id = sid
        st.session_state.tp_questions = []
        st.session_state.tp_current_q = 0
        st.session_state.tp_answers = []
        st.session_state.tp_finished = False
        st.session_state.tp_start_time = time.time() if timed else None
        # Placeholder question bank for prototype flow only.
        for i in range(NUM_QUESTIONS):
            q_text = f"{sel_test} {sel_section or ''} practice question {i+1}"
            choices = ["A", "B", "C", "D"]
            correct = "A"
            qid = test_prep.add_question(sid, sel_test, sel_section or "", q_text,
                                         choices, correct, 5, i, tx)
            st.session_state.tp_questions.append({
                "id": qid, "question": q_text, "choices": choices,
                "correct_answer": correct,
            })
        st.rerun()

elif not st.session_state.tp_finished:
    qi = st.session_state.tp_current_q
    questions = st.session_state.tp_questions

    # Timer display
    if st.session_state.tp_start_time:
        elapsed = time.time() - st.session_state.tp_start_time
        remaining = max(0, TIME_LIMIT_S - elapsed)
        mins, secs = int(remaining // 60), int(remaining % 60)
        st.markdown(f"⏱ **Time Remaining: {mins}:{secs:02d}**")
        if remaining <= 0:
            # Auto-submit remaining as unanswered
            st.session_state.tp_finished = True
            result = test_prep.finish_session(st.session_state.tp_session_id, tx)
            st.session_state.tp_result = result
            add_xp(30, f"Completed {sel_test} practice (timed out)", "test_prep")
            st.rerun()

    if qi < len(questions):
        q = questions[qi]
        st.markdown(f"**Question {qi + 1} of {len(questions)}**")
        st.markdown(f"### {q['question']}")

        choices = q["choices"] if isinstance(q["choices"], list) else json.loads(q["choices"])
        answer = st.radio("Your answer:", choices, key=f"tp_ans_{qi}")

        if st.button("Submit", key=f"tp_sub_{qi}"):
            correct = answer == q["correct_answer"]
            t_taken = time.time() - st.session_state.tp_start_time if st.session_state.tp_start_time else 0
            test_prep.record_answer(st.session_state.tp_session_id, q["id"], answer, correct, t_taken, tx)
            st.session_state.tp_answers.append({"correct": correct})
            st.session_state.tp_current_q = qi + 1
            st.rerun()
    else:
        result = test_prep.finish_session(st.session_state.tp_session_id, tx)
        st.session_state.tp_finished = True
        st.session_state.tp_result = result
        add_xp(30, f"Completed {sel_test} practice", "test_prep")
        st.rerun()
else:
    result = st.session_state.get("tp_result", {})
    section_divider("Score Report")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_card("Score", f"{result.get('score_pct', 0)}%", colour="#ffd700")
    with c2:
        stat_card("Correct", f"{result.get('correct', 0)}/{result.get('total', 0)}", colour="#40dc80")
    with c3:
        stat_card("Percentile", f"~{result.get('percentile', 50)}th", colour="#00d4ff")
    with c4:
        time_s = result.get("time_taken_s", 0)
        stat_card("Time", f"{int(time_s // 60)}m {int(time_s % 60)}s", colour="#c060ff")

    st.success("Practice session complete! Review your results above.")

    if st.button("New Practice Session"):
        st.session_state.tp_session_id = None
        st.session_state.tp_finished = False
        st.rerun()

# ─── History ──────────────────────────────────────────────────────────────────
section_divider("Session History")
history = test_prep.get_session_history(sel_test, tx)
if history:
    for s in history[:10]:
        r = json.loads(s["result_json"]) if s.get("result_json") else {}
        score = r.get("score_pct", "—")
        pct = r.get("percentile", "—")
        st.markdown(f"- **{s['test_name']}** {s.get('section', '')} | Score: {score}% | Percentile: ~{pct}th")
else:
    st.caption("No practice sessions yet.")
