# Known Risks

## Product Risks
- Route grouping is now mode-gated, but student-facing wording and progressive disclosure still need polish to reduce builder/operator jargon exposure.
- Some controls still over-promise compared to the fully wired backend behavior.
- Placement and test-prep surfaces remain partially prototype-oriented.

## Architectural Risks
- `core/database.py` is materially safer after the student, curriculum, and AI facade extractions, but route ownership is still mixed and the facade still carries bootstrap and compatibility responsibilities.
- `llm/professor.py` is now thin, but new behavior can still create pressure in `llm/professor_content.py` if page orchestration keeps expanding without backend-boundary discipline.
- `ui/professor_tabs.py` now holds the extracted Professor UI, so new page-side orchestration should move into `core/` before the helper grows into another god file.
- Nested media output paths now exist, but legacy flat exports and cache artifacts still need cleanup discipline.
- `pages/11_LLM_Setup.py` is now thinner, but route ownership is still mixed because setup and diagnostics surfaces are still directly visible in the same broad navigation context as student pages.

## Operational Risks
- `rg` is not available in the current shell environment, so inventory work should use PowerShell-native fallbacks.
- Windows filesystem locking can affect sqlite test cleanup and long-running render artifacts.
- Exports and cache folders can pollute repo scans if they are not excluded deliberately.

## First Normalization Targets
1. Truthful setup and diagnostics separation for student-facing UX.
2. Media metadata surfacing and cleanup policy for cached render artifacts.
3. Student-route copy and affordance cleanup after mode gating.

## Resolved in Current Session
- Canonical nested media output storage now exists with legacy fallback for already-rendered flat outputs.
- First `core/database.py` split slice is complete: student-facing wrappers now live in `core/db_facade_student.py` while `core/database.py` preserves the public import contract.
- `pages/03_Professor_AI.py` is now a thin route shell; tab rendering lives in `ui/professor_tabs.py` and targeted verification passed.
- Second `core/database.py` split slice is complete: curriculum-facing wrappers now live in `core/db_facade_curriculum.py` while `core/database.py` preserves the public import contract.
- Third `core/database.py` split slice is complete: AI-facing wrappers now live in `core/db_facade_ai.py` while `core/database.py` preserves the public import contract.
- The AI-facing facade now logs chat persistence and audit lifecycle events through `core.logger` without changing public imports.
- Professor backend split is complete: `llm/professor.py` now re-exports a composed `Professor` class from `llm/professor_base.py`, `llm/professor_content.py`, and `llm/professor_workflows.py`.
- LLM setup backend extraction is complete: setup probes/tests/catalog data now live in `core/llm_setup.py`, and `pages/11_LLM_Setup.py` imports that backend helper surface.
- Course-tree split is complete: course-tree concerns now live in `core/course_tree_constants.py`, `core/course_tree_queries.py`, `core/course_tree_policy.py`, `core/course_tree_competency.py`, and `core/course_tree_qualifications.py`, while `core/course_tree.py` preserves the public import contract.
- Agent tool split is complete: registry primitives now live in `llm/tool_registry.py` and category tools in `llm/tools_course.py`, `llm/tools_video.py`, and `llm/tools_utility.py`, while `llm/tools.py` preserves the public import contract.
- First-pass route ownership mode gating is complete: `core/ui_mode.py` now persists Student/Builder/Operator mode, sidebar navigation is mode-filtered, builder pages are gated to builder/operator mode, and admin/prototype pages are gated to operator mode.
