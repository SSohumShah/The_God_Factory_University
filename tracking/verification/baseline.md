# Verification Baseline

## Known Verified State
- Focused audit and qualification tests previously passed in session history.
- The repo memory requires `py_compile` after edits.
- The current workspace includes regression, contracts, import, audio, provider, database, course-tree, and end-to-end tests.

## Verification Policy
- After each code slice: run `py_compile` on all changed Python files.
- Prefer targeted pytest runs tied to the affected domain instead of broad suites first.
- Full-suite runs are reserved for stabilization checkpoints because the project is large and some runs are slow on Windows.

## Baseline Test Domains
- `tests/test_database.py`: database facade and academic persistence.
- `tests/test_course_tree.py`: qualification, prerequisite, and benchmark behavior.
- `tests/test_providers.py`: provider capabilities and audit profiles.
- `tests/test_import.py`: schema import and validation behavior.
- `tests/test_e2e.py`: integration-level happy-path coverage.
- `tests/test_contracts.py`: symbol and page contract checks.

## Current Risk Notes
- Windows teardown around SQLite WAL files may need retry-based cleanup behavior.
- Streamlit pages can behave differently under import-only checks vs. actual runtime.
- Long pytest runs should be scoped carefully to avoid wasting iteration time during active refactors.

## Latest Verified Slice
- Nested media output path slice:
	- `py_compile` passed for renderer, render pages, and new path helper.
	- `tests/test_output_paths.py` passed.
	- `tests/test_contracts.py` passed.
	- Focused result: `33 passed`.
- Student facade extraction slice:
	- `py_compile` passed for `core/database.py` and `core/db_facade_student.py`.
	- `tests/test_database.py` passed.
	- `tests/test_contracts.py` passed.
	- `tests/test_regression.py` passed.
	- Focused result: `94 passed`.
- Professor AI tab helper extraction slice:
	- `py_compile` passed for `pages/03_Professor_AI.py` and `ui/professor_tabs.py`.
	- `tests/test_contracts.py` passed.
	- `tests/test_database.py` passed.
	- Focused result: `77 passed`.
- Curriculum facade extraction slice:
	- `py_compile` passed for `core/database.py`, `core/db_facade_curriculum.py`, and `core/db_grades.py`.
	- `tests/test_database.py` passed.
	- `tests/test_course_tree.py` passed.
	- `tests/test_contracts.py` passed.
	- Focused result: `122 passed`.
- AI facade extraction slice:
	- `py_compile` passed for `core/database.py`, `core/db_facade_ai.py`, `tests/test_database.py`, `tests/test_import.py`, and `tests/test_contracts.py`.
	- `tests/test_import.py` passed.
	- `tests/test_contracts.py` passed.
	- Focused `tests/test_database.py` coverage for audit/chat/generated-content/import behavior passed.
	- Note: a broad combined pytest run was interrupted by a terminal-side `KeyboardInterrupt`, so the slice baseline records the clean isolated runs rather than the noisy combined command.
- Professor split slice:
	- `py_compile` passed for `llm/professor.py`, `llm/professor_base.py`, `llm/professor_content.py`, and `llm/professor_workflows.py`.
	- `tests/test_regression.py` passed.
	- `tests/test_contracts.py` passed.
	- Focused result: `46 passed`.
- LLM setup extraction slice:
	- `py_compile` passed for `core/llm_setup.py` and `pages/11_LLM_Setup.py`.
	- `tests/test_contracts.py` passed.
	- Focused result: `29 passed`.
- Course-tree split slice:
	- `py_compile` passed for `core/course_tree.py`, `core/course_tree_constants.py`, `core/course_tree_queries.py`, `core/course_tree_policy.py`, `core/course_tree_competency.py`, and `core/course_tree_qualifications.py`.
	- `tests/test_course_tree.py` passed.
	- `tests/test_contracts.py` passed.
	- Focused result: `74 passed`.
- Tool-registry split slice:
	- `py_compile` passed for `llm/tools.py`, `llm/tool_registry.py`, `llm/tools_course.py`, `llm/tools_video.py`, `llm/tools_utility.py`, `llm/agent.py`, and `pages/17_Agent.py`.
	- `tests/test_contracts.py` passed.
	- `tests/test_regression.py` passed.
	- Focused result: `46 passed`.
- Route-ownership mode-gating slice:
	- `py_compile` passed for `core/ui_mode.py`, `app.py`, builder pages, and operator/prototype pages.
	- `tests/test_contracts.py` passed.
	- Focused result: `29 passed`.
