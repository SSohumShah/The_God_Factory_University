# Split Plan

Prepared after the route-ownership navigation slice.

## Target 1: `core/database.py`

Current pressure:
- Approx. 601 LOC after student, curriculum, and AI facade extraction.
- Public facade is still valid, but the file now primarily mixes schema bootstrap, terms/enrollment, achievements, quests, subjects/programs, bootstrap seeding, and compatibility shims.

### Keep in `core/database.py`
- `DB_PATH`
- `_conn()`
- `tx()`
- `init_db()`
- `get_schema_version()`
- `run_migrations()`
- Top-level facade imports and re-exports

### First extraction candidate
Create `core/db_facade_student.py` for high-traffic student-facing facade functions:
- `get_setting()`
- `set_setting()`
- `add_xp()`
- `get_xp()`
- `get_level()`
- `get_progress()`
- `set_progress()`
- `count_completed()`
- `compute_gpa()`
- `credits_earned()`
- `eligible_degrees()`
- `get_academic_progress_summary()`
- `get_course_completion_audit()`
- `log_activity()`
- `get_activity_summary()`
- `get_student_world_state()`

Why first:
- These functions are used broadly by `app.py` and multiple student pages.
- They already mostly delegate to submodules, so moving the thin wrappers is low risk.
- It reduces pressure without touching import contracts for pages.

Status:
- Completed.
- `core/db_facade_student.py` now owns these wrapper implementations.
- `core/database.py` re-exports the same public names, so page and test imports remain unchanged.
- Verified by `py_compile`, `tests/test_database.py`, `tests/test_contracts.py`, and `tests/test_regression.py`.

### Second extraction candidate
Create `core/db_facade_curriculum.py` for course and study-tree access:
- `upsert_course()`
- `upsert_module()`
- `upsert_lecture()`
- `get_all_courses()`
- `get_course()`
- `get_modules()`
- `get_lectures()`
- `get_lecture()`
- `delete_course()`
- `get_child_courses()`
- `get_course_tree()`
- `get_course_depth()`
- `get_root_course()`
- `course_completion_pct()`
- `course_credit_hours()`
- `log_study_hours()`
- `get_study_hours()`
- `check_qualifications()`
- `get_qualifications()`
- `get_all_benchmarks()`
- `get_qualification_roadmap()`
- `get_pacing_for_course()`
- `record_competency_score()`
- `get_competency_profile()`
- `check_mastery()`
- `time_to_degree_estimate()`
- `get_benchmark_comparison()`

Status:
- Completed.
- `core/db_facade_curriculum.py` now owns course CRUD plus curriculum and qualification wrappers.
- `core/database.py` still re-exports the same public names, so page, tool, media, and test imports remain unchanged.
- Verified by `py_compile`, `tests/test_database.py`, `tests/test_course_tree.py`, and `tests/test_contracts.py`.

### Third extraction candidate
Create `core/db_facade_ai.py` for professor/audit/chat/import surfaces:
- `append_chat()`
- `get_chat()`
- `_save_llm_generated_canonical()`
- `get_llm_generated()`
- `mark_imported()`
- `create_course_audit_job()`
- `list_audit_jobs()`
- `get_audit_job()`
- `get_audit_packets()`
- `get_next_pending_packet()`
- `mark_audit_job_started()`
- `record_audit_packet_review()`
- `fail_audit_job()`
- `add_remediation_item()`
- `list_remediation_backlog()`
- `bulk_import_json()`

Status:
- Completed.
- `core/db_facade_ai.py` now owns chat history, generated content, audit/remediation, and bulk-import wrappers.
- `core/database.py` still re-exports the same public names, so page, professor, agent, tool, and test imports remain unchanged.
- The facade also centralizes AI-surface logging for chat persistence and audit lifecycle transitions.
- Verified by `py_compile`, `tests/test_import.py`, `tests/test_contracts.py`, and focused `tests/test_database.py` coverage for audit/chat/generated-content/import behavior.

## Target 2: `pages/03_Professor_AI.py`

Current pressure:
- Approx. 140 LOC route shell after helper extraction.
- Page owns provider status, world-state cards, tab wiring, chat workflow, curriculum generation, grading, quiz generation, research, audit workbench, history, and app guide in one file.

### Keep in page
- `inject_theme()`
- `gf_header()`
- provider/model resolution
- top summary cards
- tab creation
- per-tab function calls

### First extraction candidate
Create `ui/professor_tabs.py` or `pages/professor_ui.py` with rendering helpers:
- `render_professor_chat_tab(...)`
- `render_curriculum_tab(...)`
- `render_grade_tab(...)`
- `render_quiz_tab(...)`
- `render_rabbit_hole_tab(...)`
- `render_audit_tab(...)`
- `render_history_tab(...)`
- `render_app_guide_tab(...)`

Why first:
- This keeps Streamlit UI code out of the main page shell without moving business logic into the page layer.
- The page becomes a route shell that wires shared state into focused render functions.

Status:
- Completed.
- `ui/professor_tabs.py` now owns the tab rendering helpers.
- `pages/03_Professor_AI.py` is reduced to provider/status cards, tab wiring, and helper calls.
- Verified by `py_compile`, `tests/test_contracts.py`, and `tests/test_database.py`.

### Second extraction candidate
Create `core/professor_workflows.py` for repeated page-side orchestration:
- session history loading/saving helpers
- audit queue execution helper
- remediation course import helper
- curriculum generation/import helper
- professor telemetry logging helper

Constraint:
- Keep page-only rendering in UI modules.
- Keep backend state mutations and orchestration in `core/`.

## Target 3: `llm/professor.py`

Current pressure:
- Previously ~730 LOC with mixed responsibilities: context/history plumbing, JSON repair, tutoring and grading, curriculum generation, decomposition, and verification workflows.

### Extraction plan
Create focused internal Professor modules while preserving public `Professor` import:
- `llm/professor_base.py`:
	- `ProfessorResponse`
	- `PROFESSOR_SYSTEM`
	- config/history/context plumbing
	- JSON repair and response wrapping
	- `ask()` and `stream()`
- `llm/professor_content.py`:
	- tutoring, grading, quiz/research, app-guide, audit packet methods
- `llm/professor_workflows.py`:
	- chunked curriculum and decomposition/jargon/verification workflows
- Keep `llm/professor.py` as thin public facade:
	- `class Professor(...)`
	- export `Professor`, `ProfessorResponse`, `PROFESSOR_SYSTEM`

Status:
- Completed.
- `llm/professor.py` now acts as a thin facade over the extracted modules.
- Public import contract remains unchanged for pages, tools, scripts, and regression tests.
- Verified by `py_compile`, `tests/test_regression.py`, and `tests/test_contracts.py`.

## Target 5: `core/course_tree.py`

Current pressure before extraction:
- Previously ~569 LOC with mixed responsibilities: constants/table bootstrap, recursive tree queries, hours and credits, assignment policy defaults, competency tracking, and qualification/benchmark evaluation.

### Extraction plan
Create focused academic helpers while preserving the public import contract:
- `core/course_tree_constants.py`:
	- standards/constants (`CREDIT_HOUR_RATIO`, AI policy levels, Bloom levels, pacing options)
	- benchmark seed data
	- `create_tables()` and `seed_benchmarks()`
- `core/course_tree_queries.py`:
	- recursive tree and parent/child queries
	- completion and hour aggregation
	- study-hour log helpers
- `core/course_tree_policy.py`:
	- assignment AI policy defaults and stored-policy resolution
- `core/course_tree_competency.py`:
	- competency score persistence
	- profile and mastery checks
- `core/course_tree_qualifications.py`:
	- benchmark/qualification evaluation and roadmap/comparison helpers
- Keep `core/course_tree.py` as a thin public facade that re-exports all legacy symbols.

Status:
- Completed.
- `core/course_tree.py` is now a thin re-export facade; compatibility imports in `core/database.py` and tests remain unchanged.
- Focused verification passed: `py_compile` on split modules and `tests/test_course_tree.py` + `tests/test_contracts.py` (`74 passed`).

## Target 6: `llm/tools.py`

Current pressure before extraction:
- Previously ~581 LOC with mixed responsibilities: tool registry primitives plus course/video/utility tool implementations.

### Extraction plan
Preserve the public import contract (`llm.tools`) while splitting by concern:
- `llm/tool_registry.py`:
	- `Tool` dataclass
	- registry map
	- `register()`, `get_tool()`, `list_tools()`, `get_schemas()`, `call_tool()`
- `llm/tools_course.py`:
	- course and assignment tools
	- lecture-quiz generation helper tool
- `llm/tools_video.py`:
	- scene list/edit/add/remove/reorder
	- narration enhancement and render trigger
- `llm/tools_utility.py`:
	- non-mutating utility tool(s)
- Keep `llm/tools.py` as a thin facade that re-exports registry APIs and imports tool modules for registration side effects.

Status:
- Completed.
- `llm/tools.py` is now a thin facade over `llm/tool_registry.py` and category modules.
- Public imports used by `llm/agent.py` and `pages/17_Agent.py` remain unchanged.
- Focused verification passed: `py_compile` and `tests/test_contracts.py` + `tests/test_regression.py` (`46 passed`).

## Recommended Order
1. Normalize route ownership and navigation.
2. Only then add more student-route feature work or broader AI/product expansion.

## Target 4: `pages/11_LLM_Setup.py`

Current pressure before extraction:
- ~571 LOC with mixed responsibilities: UI wizard rendering, hardware detection, provider test calls, local-service probes, and large provider/model catalog constants.

### Extraction plan
Create `core/llm_setup.py` for backend setup helpers:
- `detect_hardware()`
- `get_current_llm_config()`
- `test_provider()`
- `check_local_service()`
- `ping_local_health()`
- `OLLAMA_CATALOG`
- `CLOUD_PROVIDERS`

Status:
- Completed.
- `pages/11_LLM_Setup.py` now imports backend helpers and provider catalogs from `core/llm_setup.py`.
- Page behavior and contract remain unchanged while backend logic is centralized.
- Verified by `py_compile` and `tests/test_contracts.py`.
