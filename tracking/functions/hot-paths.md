# Hot Paths

Only high-value execution paths are tracked here.

## Academic Progress Path
- `core/database.py`: facade entry points for progress, assignments, grades, audit jobs, and world state.
- `core/db_grades.py`: verified credits, GPA, degree eligibility, and course completion audit.
- `core/course_tree.py`: public compatibility facade for course-tree imports.
- `core/course_tree_queries.py`: completion and hour/credit aggregation hot path.
- `core/course_tree_competency.py`: Bloom-level profile/mastery checks used by qualification logic.
- `core/course_tree_qualifications.py`: benchmark evidence, progress status, and roadmap/comparison behavior.

## Professor Path
- `llm/professor.py`: public import surface for Professor behavior.
- `llm/professor_base.py`: chat history, context budgeting seam, and JSON repair.
- `llm/professor_content.py`: chat/grading/quiz/rabbit-hole/audit packet behavior.
- `llm/professor_workflows.py`: decomposition, jargon, and chunked curriculum workflows.
- `llm/tools.py`: public import facade for agent tool APIs.
- `llm/tool_registry.py`: tool registration and dispatch hot path used by agent execution.
- `llm/tools_course.py`, `llm/tools_video.py`, `llm/tools_utility.py`: category-specific tool handlers used by `call_tool()`.
- `llm/providers.py`: provider request dispatch and capability differences.
- `llm/model_profiles.py`: chunk sizing, audit passes, and ETA assumptions.

## Media Path
- `media/video_engine.py`: scene clip creation and lecture render output.
- `media/audio_engine.py`: narration synthesis and audio layers.
- `pages/02_Lecture_Studio.py`, `pages/04_Timeline_Editor.py`, `pages/05_Batch_Render.py`: current UI entry points that should eventually rely on thinner backend orchestration.

## Support Path
- `core/help_registry.py` and `pages/10_Help.py`: user-facing help routing.
- `core/app_docs.py` and `llm/professor.py`: professor-readable product guidance.
- `pages/11_LLM_Setup.py`: provider onboarding and setup explanation.
- `core/ui_mode.py` and `app.py`: mode persistence and route gating for student/builder/operator surfaces.
