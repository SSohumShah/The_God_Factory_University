# Domain Map

## UI Shell
- `app.py`: dashboard and entry navigation.
- `pages/`: thin wrappers are the target architecture, but several pages still own too much workflow logic.
- `ui/theme.py`: visual helpers, status widgets, and help link rendering.
- `core/ui_mode.py`: persisted Student/Builder/Operator mode and page-level route gates.

## Academic Core
- `core/database.py`: public facade and schema/init entry point.
- `core/db_assignments.py`: submission and grading-state persistence.
- `core/db_grades.py`: GPA, verified credits, and degree logic.
- `core/course_tree.py`: thin public facade for course-tree exports.
- `core/course_tree_constants.py`: standards/constants plus benchmark bootstrap.
- `core/course_tree_queries.py`: recursive tree traversal and hour/credit aggregation helpers.
- `core/course_tree_policy.py`: assignment AI policy defaults and policy resolution.
- `core/course_tree_competency.py`: Bloom-level competency persistence and mastery checks.
- `core/course_tree_qualifications.py`: benchmark and qualification evidence evaluation.
- `core/db_programs.py`, `core/db_subjects.py`, `core/db_levels.py`: seeded academic structure that is underused by the UI.
- `core/university.py`: dormant infrastructure including flashcards, study sessions, notes, certificates, calendar, and spaced repetition.

## AI Layer
- `llm/providers.py`: provider catalog, capabilities, and connection behavior.
- `llm/model_profiles.py`: model-aware audit constraints and ETA rules.
- `llm/professor.py`: thin public Professor facade.
- `llm/professor_base.py`: config/history/context and JSON repair seams.
- `llm/professor_content.py`: tutoring, grading, app-guide, and packet audit behavior.
- `llm/professor_workflows.py`: chunked curriculum and decomposition workflows.
- `llm/context_manager.py`: token budgeting and context shaping.
- `llm/tools.py`: thin public facade for agent tool imports.
- `llm/tool_registry.py`: tool registration and invocation primitives.
- `llm/tools_course.py`, `llm/tools_video.py`, `llm/tools_utility.py`: category-specific agent tool implementations.

## Media Layer
- `media/audio_engine.py`: TTS, ambiance, binaural, SFX.
- `media/video_engine.py`: scene rendering, file output, and MoviePy composition.
- `media/output_paths.py`: canonical nested media output path resolution and metadata writing.

## Support Layer
- `core/help_registry.py` and `core/app_docs.py`: contextual help and professor-readable app explanations.
- `pages/10_Help.py` and `pages/11_LLM_Setup.py`: support and setup surfaces.
- `pages/09_Diagnostics.py`: operator diagnostics living too close to the student route.

## Boundary Risks
- Route ownership is mixed: student, builder, and operator pages coexist without clear isolation.
- Some pages still reach beyond the facade model in practice and should be audited during normalization.
- Media and AI pages combine workflow orchestration, diagnostics, and product UI in the same file.
