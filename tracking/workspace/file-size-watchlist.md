# File Size Watchlist

Source-only line counts from the current Band 1 inventory.

## Highest Pressure
- `core/database.py`: 601
- `core/university.py`: 532
- `media/video_engine.py`: 479
- `ui/professor_tabs.py`: 473
- `core/help_registry.py`: 460
- `llm/model_profiles.py`: 446
- `tests/test_course_tree.py`: 445
- `pages/11_LLM_Setup.py`: 372
- `ui/theme.py`: 358
- `llm/tools_course.py`: 262
- `llm/professor_content.py`: 259
- `llm/tools_video.py`: 242
- `core/llm_setup.py`: 210
- `core/course_tree_qualifications.py`: 220
- `llm/professor_base.py`: 243
- `llm/professor_workflows.py`: 192
- `llm/tool_registry.py`: 55
- `llm/tools_utility.py`: 24
- `llm/tools.py`: 22
- `llm/professor.py`: 8
- `core/course_tree_queries.py`: 120
- `core/course_tree_constants.py`: 85
- `core/course_tree.py`: 81
- `core/course_tree_competency.py`: 69
- `core/course_tree_policy.py`: 57
- `core/db_facade_ai.py`: 184
- `core/db_facade_student.py`: 159
- `core/db_facade_curriculum.py`: 142
- `pages/03_Professor_AI.py`: 140

## Watch Rules
- Any file at or above 700 LOC is a split candidate before meaningful new feature work.
- Any file at or above 500 LOC should only receive small changes unless part of an explicit split slice.
- `chat1.md`, `spec.md`, `plan1.md`, and checklist files are large documentation artifacts but not code pressure points.

## Current Split Priorities
1. Route ownership and navigation normalization in `app.py`/`pages/`
2. `ui/professor_tabs.py` only if new Professor UI growth resumes
3. Reassess `llm/professor_content.py` only if new behavior pushes it near 500 LOC
