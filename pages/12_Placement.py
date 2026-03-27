"""
Placement Testing — adaptive placement exam with AI-generated questions.
"""

import sys
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import (
    get_subject_domains, get_subject_children, get_grade_levels,
    get_setting, set_setting, add_xp, tx,
)
from core.ui_mode import require_ui_mode
from core import placement
from ui.theme import inject_theme, gf_header, section_divider, stat_card, help_button

inject_theme()
require_ui_mode(("operator",), "Placement Testing")
gf_header("Placement Testing", "Discover your starting level in any subject.")
help_button("placement-testing")
st.warning("Prototype status: placement questions are still placeholder-generated. Use results as rough practice signals, not official placement decisions.")

# ─── Subject Selection ────────────────────────────────────────────────────────
section_divider("Choose Subject")

domains = get_subject_domains()
domain_names = [d["name"] for d in domains]
domain_ids = [d["id"] for d in domains]

if not domains:
    st.warning("No subjects found. Please restart the application.")
    st.stop()

sel_idx = st.selectbox("Domain", range(len(domain_names)), format_func=lambda i: domain_names[i])
selected_domain = domains[sel_idx]
children = get_subject_children(selected_domain["id"])

subject_id = selected_domain["id"]
if children:
    child_names = [selected_domain["name"] + " (General)"] + [c["name"] for c in children]
    child_ids = [selected_domain["id"]] + [c["id"] for c in children]
    sub_idx = st.selectbox("Specific Field", range(len(child_names)), format_func=lambda i: child_names[i])
    subject_id = child_ids[sub_idx]

# ─── Test State Management ────────────────────────────────────────────────────
if "pt_test_id" not in st.session_state:
    st.session_state.pt_test_id = None
    st.session_state.pt_questions = []
    st.session_state.pt_current_q = 0
    st.session_state.pt_answers = []
    st.session_state.pt_finished = False

# ─── Start / Resume Test ─────────────────────────────────────────────────────
section_divider("Placement Exam")

NUM_QUESTIONS = 10

if st.session_state.pt_test_id is None:
    st.info(f"This adaptive exam has {NUM_QUESTIONS} questions. Difficulty adjusts based on your answers.")
    if st.button("Begin Placement Exam", type="primary"):
        test_id = placement.start_test(subject_id, tx)
        st.session_state.pt_test_id = test_id
        st.session_state.pt_questions = []
        st.session_state.pt_current_q = 0
        st.session_state.pt_answers = []
        st.session_state.pt_finished = False
        # Placeholder question bank for prototype flow only.
        _difficulties = [3, 4, 5, 5, 6, 6, 7, 7, 8, 9]
        for i in range(NUM_QUESTIONS):
            diff = _difficulties[i]
            q_text = f"Placement question {i+1} for {subject_id} (difficulty {diff}/10)"
            choices = ["Option A", "Option B", "Option C", "Option D"]
            correct = "Option A"
            qid = placement.add_question(test_id, q_text, choices, correct, diff, i, tx)
            st.session_state.pt_questions.append({
                "id": qid, "question": q_text, "choices": choices,
                "correct_answer": correct, "difficulty": diff,
            })
        st.rerun()
elif not st.session_state.pt_finished:
    qi = st.session_state.pt_current_q
    questions = st.session_state.pt_questions

    if qi < len(questions):
        q = questions[qi]
        st.markdown(f"**Question {qi + 1} of {len(questions)}** — Difficulty: {'⬥' * q['difficulty']}{'⬦' * (10 - q['difficulty'])}")
        st.markdown(f"### {q['question']}")

        choices = q["choices"] if isinstance(q["choices"], list) else json.loads(q["choices"])
        answer = st.radio("Your answer:", choices, key=f"pt_ans_{qi}")

        if st.button("Submit Answer", key=f"pt_submit_{qi}"):
            correct = answer == q["correct_answer"]
            placement.record_answer(st.session_state.pt_test_id, q["id"], answer, correct, 0, tx)
            st.session_state.pt_answers.append({"correct": correct, "answer": answer})
            st.session_state.pt_current_q = qi + 1
            st.rerun()
    else:
        # All questions answered
        result = placement.finish_test(st.session_state.pt_test_id, tx)
        st.session_state.pt_finished = True
        st.session_state.pt_result = result
        add_xp(50, "Completed placement exam", "placement")
        st.rerun()
else:
    # Show results
    result = st.session_state.get("pt_result", {})
    section_divider("Results")

    c1, c2, c3 = st.columns(3)
    with c1:
        stat_card("Score", f"{result.get('score_pct', 0)}%", colour="#ffd700")
    with c2:
        stat_card("Correct", f"{result.get('correct', 0)}/{result.get('total', 0)}", colour="#40dc80")
    with c3:
        stat_card("Recommended Level", result.get("recommended_level", "N/A"), colour="#c060ff")

    st.success(f"Based on your performance, we recommend starting at the **{result.get('recommended_level', 'intermediate')}** level.")

    if st.button("Take Another Exam"):
        st.session_state.pt_test_id = None
        st.session_state.pt_finished = False
        st.rerun()

# ─── Past Tests ───────────────────────────────────────────────────────────────
section_divider("Test History")
past = placement.get_all_tests(tx)
if past:
    for t in past[:10]:
        status = t.get("status", "unknown")
        result_data = json.loads(t["result_json"]) if t.get("result_json") else {}
        score = result_data.get("score_pct", "—")
        st.markdown(f"- **{t['id'][:16]}** | Subject: {t.get('subject_id', '?')} | Status: {status} | Score: {score}%")
else:
    st.caption("No placement tests taken yet.")
