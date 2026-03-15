# Development Instructions for The God Factory University

These are mandatory rules for all future development on this project.
Every coding session must follow these instructions exactly.

---

## RULE 1: Hard 1000 LOC Limit Per File

No Python file may exceed 1000 lines of code. Ever.

**Why:** LLM context windows break on massive files. Files over 1000 LOC cannot be
reliably read, understood, and edited in a single context. Small files mean every
file can be fully loaded, edited, and verified without truncation.

**Enforcement:**
- Before adding code to any file, check its current line count
- If a file would exceed 800 LOC after your changes, split it FIRST
- If a file already exceeds 1000 LOC, refactoring it down is the highest priority before any new work

**Current file sizes (baseline):**
```
898  core/database.py         <- WATCH (primary facade, delegated sub-modules)
758  llm/professor.py
639  llm/tools.py
636  core/university.py
621  core/course_tree.py
556  media/video_engine.py
550  pages/11_LLM_Setup.py
467  llm/agent.py
445  scripts/generate_curriculum.py
423  ui/theme.py
405  core/help_registry.py
403  pages/03_Professor_AI.py
379  llm/providers.py
362  media/audio_engine.py
342  core/app_docs.py
281  pages/06_Grades.py
266  pages/09_Diagnostics.py
258  pages/17_Agent.py
241  llm/context_manager.py
239  core/decomposition.py
230  pages/01_Library.py
228  app.py
214  pages/02_Lecture_Studio.py
212  pages/05_Batch_Render.py
198  pages/08_Settings.py
```

---

## RULE 2: Modular Architecture with Sub-Hierarchies

Every feature must be broken into granular methods in dedicated modules.
Pages are thin UI wrappers — they call backend functions, they don't contain business logic.

### Directory Structure (current + expansion pattern)

```
app.py                          <- Dashboard entry point (thin)
core/
    __init__.py
    database.py                 <- DB schema, init, core CRUD (facade)
    db_achievements.py          <- Achievement defs, seeding, triggers
    db_activity.py              <- Activity logging & student profile
    db_assignments.py           <- Assignment CRUD, submission, prove-it flagging
    db_grades.py                <- GPA, grade scale, degree tracks
    db_import.py                <- Bulk JSON import, schema validation
    db_levels.py                <- Grade level system (K-postdoc)
    db_programs.py              <- Degree programs & enrollments
    db_quests.py                <- Weekly quest logic
    db_shims.py                 <- Compatibility aliases for UI pages
    db_subjects.py              <- Subject taxonomy (domain/field/subfield)
    course_tree.py              <- Recursive courses, qualifications, competency
    decomposition.py            <- Decomposition prompts, pacing templates
    university.py               <- University infrastructure tables
    help_registry.py            <- Help text entries
    app_docs.py                 <- Professor-readable documentation
    placement.py                <- Placement test engine
    test_prep.py                <- Standardized test prep engine
    chat_store.py               <- Chat persistence to disk
llm/
    __init__.py
    providers.py                <- LLM provider abstraction + config
    professor.py                <- Professor AI agent
    agent.py                    <- Autonomous agent loop
    tools.py                    <- Agent tool definitions
    context_manager.py          <- LLM context management
    professor_prompts.py        <- System prompts, prompt templates (split when needed)
    json_repair.py              <- LLM response JSON repair utility (future)
media/
    audio_engine.py             <- TTS, binaural, ambient, SFX
    audio_normalize.py          <- Loudness normalization, clipping detection (future)
    video_engine.py             <- Animated video renderer
    video_profiles.py           <- Render quality profiles (future, or split from video_engine)
    scene_builder.py            <- Scene-level clip composition (split from video_engine when needed)
ui/
    __init__.py
    theme.py                    <- CSS, widget helpers, layout components
    widgets.py                  <- Reusable widget components (split from theme.py when needed)
    charts.py                   <- Chart/graph components for statistics (future)
pages/
    01_Library.py               <- Course browsing and import
    02_Lecture_Studio.py         <- Lecture playback and rendering
    03_Professor_AI.py          <- Professor AI chat and tools
    04_Timeline_Editor.py       <- Scene reordering
    05_Batch_Render.py          <- Batch render queue
    06_Grades.py                <- GPA, transcript, degrees
    07_Achievements.py          <- XP, badges, levels
    08_Settings.py              <- All configuration
    09_Diagnostics.py           <- System health checks
    10_Help.py                  <- Help page
    11_LLM_Setup.py             <- Provider setup wizard
    12_Placement.py             <- Placement tests (future)
    13_Test_Prep.py             <- Standardized test prep (future)
    14_Profile.py               <- Student profile (future)
    15_Statistics.py            <- Analytics dashboard (future)
tests/
    __init__.py
    test_database.py            <- DB CRUD tests
    test_import.py              <- JSON import/validation tests
    test_audio.py               <- Audio generation tests
    test_render.py              <- Minimal render smoke test
    test_professor.py           <- Mocked professor prompt tests
    test_contracts.py           <- Page symbol import validation
```

### Split Rules

When a file approaches 800 LOC, split it using this pattern:

1. **Identify clusters** — group related functions (e.g., all grade-related DB queries)
2. **Create the sub-module** — e.g., `core/db_grades.py`
3. **Move functions** — cut from the original, paste into the new module
4. **Re-export from the original** — add `from core.db_grades import *` or explicit names in `database.py`
5. **No page changes needed** — pages still import from the same top-level module
6. **Verify** — run `py_compile` on both files + all importing pages

Example for splitting `database.py`:
```python
# core/database.py (stays as the public API)
from core.db_courses import get_all_courses, bulk_import_json, delete_course, ...
from core.db_grades import get_grades, get_gpa, get_credits, eligible_degrees, ...
from core.db_achievements import get_xp, get_level, award_xp, get_achievements, ...
from core.db_settings import get_setting, save_setting, ...

# Schema init, connection helper, and migration logic stay here
```

---

## RULE 3: Granular Functions, Single Responsibility

Every function does ONE thing. No god functions.

- Maximum function length: ~50 lines (soft limit, but strive for it)
- If a function has more than 3 levels of nesting, break out the inner logic
- Every function that could be reused goes in a backend module, not in a page file
- Page files should read like a script: call function, display result, call function, display result

**Pattern:**
```python
# BAD — business logic in page file
def render_grades_page():
    conn = get_connection()
    rows = conn.execute("SELECT ...").fetchall()
    gpa = sum(r[1] * r[2] for r in rows) / sum(r[2] for r in rows)
    # ... 80 more lines of calculation + display mixed together

# GOOD — page calls backend, displays result
from core.database import get_grades, get_gpa, eligible_degrees
grades = get_grades()
gpa = get_gpa()
degrees = eligible_degrees()
display_gpa_card(gpa)
display_degree_progress(degrees)
```

---

## RULE 4: Feature Implementation Workflow

For every new feature, follow this exact sequence:

1. **Check the checklists** — find the relevant items in check1-4.md
2. **Check file sizes** — will this push any file over 800 LOC?
3. **Split first if needed** — refactor before adding, never after
4. **Create backend logic** — functions in `core/`, `llm/`, `media/`, etc.
5. **Create/update the page** — thin UI layer that calls the backend
6. **Add help entry** — register in `core/help_registry.py` if user-facing
7. **Compile check** — `python -m py_compile <file>` for every changed file
8. **Update checklist** — mark items `[x]` in the relevant checklist
9. **Git commit** — atomic commit with descriptive message covering what changed

---

## RULE 5: Database Evolution

The database will grow significantly. Follow these rules:

- **Schema changes** go through `init_db()` with `CREATE TABLE IF NOT EXISTS`
- **New tables** for new domains (placement_tests, subjects, programs, activity_log, etc.)
- **No ALTER TABLE** — use `IF NOT EXISTS` for columns where possible, or migration functions
- **Migration functions** — when schema must change, add a versioned migration in `database.py`
- **Query functions** — one function per query pattern. No raw SQL in page files.
- **Connection safety** — always use the `_conn()` context manager
- **When database.py exceeds 800 LOC** — split into `db_courses.py`, `db_grades.py`, etc. (see Rule 2)

---

## RULE 6: No Emojis Anywhere

The project uses a dark-academic ASCII theme. No emojis in:
- UI text
- Code comments
- Help entries
- Error messages
- README or docs

Use ASCII art, decorative characters, and bracket-style markers instead:
`[OK]`, `[!!]`, `[?]`, `[>]`, `[*]`, `>>>`, `---`, `===`, `+++`

---

## RULE 7: Import and Dependency Discipline

- **No circular imports** — backend modules never import from pages or UI
- **Dependency direction:** pages -> ui -> core/llm/media. Never reverse.
- **New pip packages** must be added to `requirements.txt` with pinned versions
- **Lazy imports** for heavy modules (MoviePy, edge_tts) — import inside functions, not at module top
- **Type hints** on all new public functions (parameters and return type)
- **`from __future__ import annotations`** in any file using `X | Y` union syntax (Python 3.9 compat)

---

## RULE 8: Page File Conventions

Every page file follows this template:

```python
"""
Page title — one-line description.
"""
from __future__ import annotations
import streamlit as st
from core.database import ...
from ui.theme import inject_theme, gf_header, section_divider, help_button

inject_theme()

# Sidebar is handled by app.py — pages just render their content

gf_header("Page Title", "Subtitle text")
help_button("page-topic-key")

# ... page content using backend functions and theme widgets ...
```

- No business logic in page files
- No raw SQL
- No direct file I/O (use backend functions)
- Help button at the top of every page and at every major section

---

## RULE 9: Testing Strategy

Tests live in `tests/` and follow these patterns:

- **Unit tests** — test individual functions in isolation (DB CRUD, audio gen, etc.)
- **Contract tests** — verify every symbol imported by page files actually exists
- **Smoke tests** — run minimal end-to-end flows (import course, render 1 lecture, etc.)
- **No external dependencies in tests** — mock LLM providers, use temp DBs
- **Run with:** `python -m pytest tests/` from project root

---

## RULE 10: Checklist-Driven Development

The four checklists define ALL work:

| Checklist | Scope | Items |
|-----------|-------|-------|
| check1.md | Product roadmap — features, milestones, release gates | ~90 items |
| check2.md | Engineering contract — API integrity, testing, ops | ~80 items |
| check3.md | Academic vision — K-Doctorate, test prep, curricula | ~721 items |
| check4.md | Gap analysis — bridges checklists, phased priority | ~230 items |

**Priority order for development:**
1. Phase E (check4) — Core quality gaps: import validation, render reliability, provider errors, testing
2. Phase D (check4) — Academic infrastructure: subjects, placement, profiles, statistics
3. check1/check2 remaining — Product/engineering items not covered by check4
4. check3 Phases 0-2 — Academic architecture, placement engine, test prep
5. check3 Phases 3-7 — Full curriculum, unsolved problems, behavioral analytics

**Within each phase, work in this order:**
1. Database schema additions (backend first)
2. Core logic functions (business logic)
3. Page UI wiring (thin display layer)
4. Help entries (discoverability)
5. Tests (verification)
6. Checklist updates (tracking)

---

## RULE 11: Git Hygiene

- **Atomic commits** — one feature or fix per commit
- **Descriptive messages** — what changed and why, not "update files"
- **No generated files** — exports/, .venv/, __pycache__/, *.db stay in .gitignore
- **Push after each working session** — don't accumulate unpushed work

---

## RULE 12: Error Handling Philosophy

- **Validate at boundaries** — user input, LLM responses, file I/O, external APIs
- **Trust internal code** — don't add defensive checks between your own modules
- **User-friendly errors** — never show raw tracebacks in Streamlit UI
- **Structured error returns** — functions return `(result, warnings)` tuples for operations that can partially fail
- **LLM output safety** — always sanitize LLM responses before rendering with `st.markdown`

---

## Quick Reference: Pre-Flight Checklist (Before Every Session)

```
[ ] Read this file (DEVELOPMENT.md)
[ ] Check current file sizes: which files are approaching 800 LOC?
[ ] Pick next items from check4.md (priority order: E -> D -> check1/2 -> check3)
[ ] For each item: backend first, page second, help entry third, test fourth
[ ] After each file edit: py_compile check
[ ] After each feature: update checklist, git commit
[ ] End of session: git push
```
