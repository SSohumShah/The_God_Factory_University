# TGFU Workspace Census

Updated from Band 1 startup mapping.

## Top-Level Structure
- `app.py`: Streamlit dashboard entry and top-level navigation surface.
- `pages/`: student, builder, operator, and diagnostics UI surfaces.
- `core/`: database facade plus academic, import, help, placement, and test-prep logic.
- `llm/`: provider abstraction, professor behavior, agent loop, tools, and context management.
- `media/`: audio and video generation pipeline.
- `ui/`: theme helpers and shared UI utilities.
- `schemas/`: course and assignment contract files.
- `tests/`: regression, contract, database, import, audio, provider, and end-to-end tests.
- `checklists/`: roadmap, engineering, gap analysis, and expansion planning.
- `tracking/`: machine-readable development scaffolding for long-horizon work.

## Current Product Surfaces
- Student route is mixed with builder and operator pages.
- Builder tools are present in `pages/01_Library.py`, `pages/04_Timeline_Editor.py`, `pages/05_Batch_Render.py`, and `pages/17_Agent.py`.
- Operator/support surfaces are present in `pages/09_Diagnostics.py`, `pages/10_Help.py`, and `pages/11_LLM_Setup.py`.
- Academic integrity and audit infrastructure already exists in `core/db_grades.py`, `core/db_audit.py`, `core/course_tree.py`, and `llm/model_profiles.py`.

## Band 1 Observations
- The repo is large enough that summary-led execution is necessary.
- The current pressure points are architectural, not just feature gaps.
- The next band should prefer normalization of route ownership, facade boundaries, and output storage before broad new features.

## Immediate Candidate Slices
1. Student-safe separation of diagnostics and setup surfaces.
2. Media metadata surfacing and cleanup policy for cached render artifacts.

## Completed Slices
- Slice 1: canonical nested media export paths with legacy playback fallback.
	- Added `media/output_paths.py`.
	- Renderer now writes nested outputs under `exports/{course_id}/{module_id}/...`.
	- Lecture Studio, Timeline Editor, and Batch Render now pass enough context to resolve nested outputs.
	- Legacy flat-path lookup remains supported for already-rendered videos.
- Slice 2: student-facing database facade extraction.
	- Added `core/db_facade_student.py` with settings, XP, progress, academic summary, and activity/world-state wrappers.
	- `core/database.py` remains the public facade but now re-exports those wrappers from the extracted module.
	- Verified with `py_compile`, `tests/test_database.py`, `tests/test_contracts.py`, and `tests/test_regression.py`.
- Slice 3: Professor AI route-shell extraction.
	- Added `ui/professor_tabs.py` with focused render helpers for chat, curriculum, grading, quiz, research, audit, history, and guide tabs.
	- `pages/03_Professor_AI.py` now stays focused on theme/header, provider state, summary cards, tab creation, and helper wiring.
	- Verified with `py_compile`, `tests/test_contracts.py`, and `tests/test_database.py`.
- Slice 4: curriculum-facing database facade extraction.
	- Added `core/db_facade_curriculum.py` with course CRUD plus curriculum, qualification, pacing, and competency wrappers.
	- `core/database.py` remains the public facade but now re-exports those wrappers from the extracted module.
	- Verified with `py_compile`, `tests/test_database.py`, `tests/test_course_tree.py`, and `tests/test_contracts.py`.
- Slice 5: AI-facing database facade extraction.
	- Added `core/db_facade_ai.py` with chat history, LLM-generated content, audit/remediation, and bulk-import wrappers.
	- `core/database.py` remains the public facade but now re-exports those wrappers from the extracted module.
	- Added structured logging at the AI facade edge for chat persistence and audit lifecycle events.
	- Verified with `py_compile`, `tests/test_import.py`, `tests/test_contracts.py`, and focused `tests/test_database.py` coverage for audit/chat/generated-content/import paths.
- Slice 6: Professor backend module split.
	- Added `llm/professor_base.py`, `llm/professor_content.py`, and `llm/professor_workflows.py`.
	- Reduced `llm/professor.py` to a thin public facade that preserves `Professor` and `ProfessorResponse` imports.
	- Preserved regression-critical behaviors like `Professor.repair_json`, chat history flow, and chunked generation methods.
	- Verified with `py_compile`, `tests/test_regression.py`, and `tests/test_contracts.py`.
- Slice 7: LLM setup backend extraction.
	- Added `core/llm_setup.py` to own hardware detection, provider test calls, local-service probes, and provider/model catalog data.
	- Reduced `pages/11_LLM_Setup.py` by removing duplicated backend helper logic and in-page catalog constants.
	- Preserved setup-page UI behavior and provider save/test flow.
	- Verified with `py_compile` and `tests/test_contracts.py`.
- Slice 8: course-tree helper split.
	- Added `core/course_tree_constants.py`, `core/course_tree_queries.py`, `core/course_tree_policy.py`, `core/course_tree_competency.py`, and `core/course_tree_qualifications.py`.
	- Reduced `core/course_tree.py` to a thin re-export facade while preserving public symbol imports.
	- Preserved `core.database` and test import compatibility.
	- Verified with `py_compile`, `tests/test_course_tree.py`, and `tests/test_contracts.py`.
- Slice 9: tool-registry helper split.
	- Added `llm/tool_registry.py`, `llm/tools_course.py`, `llm/tools_video.py`, and `llm/tools_utility.py`.
	- Reduced `llm/tools.py` to a thin facade that preserves public import names while loading tool modules via side-effect imports.
	- Preserved compatibility for `llm/agent.py` and `pages/17_Agent.py` imports.
	- Verified with `py_compile`, `tests/test_contracts.py`, and `tests/test_regression.py`.
- Slice 10: first-pass route ownership mode gating.
	- Added `core/ui_mode.py` for persisted Student/Builder/Operator mode helpers.
	- Sidebar mode selector now filters visible navigation groups by mode in `app.py`.
	- Builder pages (`01`, `04`, `05`, `17`) now require builder/operator mode.
	- Admin/prototype pages (`09`, `12`, `13`, `18`) now require operator mode.
	- Verified with `py_compile` and `tests/test_contracts.py`.
