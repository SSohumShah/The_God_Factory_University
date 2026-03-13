# AI University Project Checklist (Product Roadmap + Delivery)

This checklist is aligned to the current Streamlit + SQLite + local-first architecture.
Cross-reference: [check2.md](check2.md) covers the engineering contract and integration verification.

## 1. Foundation and Stability
- [x] Multipage app scaffold is active (`app.py` + `pages/`)
- [x] Core persistence layer exists (`core/database.py`) with WAL mode and foreign keys
- [x] JSON curriculum import pipeline exists (`bulk_import_json`)
- [x] FFmpeg strategy switched to bundled `imageio-ffmpeg` (no system install dependency)
- [x] All runtime signature mismatches resolved via compatibility shims in `database.py`
- [x] All 8 pages compile cleanly (`py_compile` pass)
- [x] All 6 core modules import cleanly (database, providers, professor, audio, video, theme)
- [x] `video_engine.py` indentation corruption resolved (4 duplicate blocks removed)
- [x] `from __future__ import annotations` added where needed for Python 3.9 compat
- [x] Verify no traceback on first launch with empty DB (Streamlit runtime test)
- [x] Add startup self-check panel (db, ffmpeg, tts, llm, video, audio — expandable on Dashboard)

## 2. Academic Structure (University Requirements)
- [x] Degree tracks defined: Certificate(15cr) -> Associate(60cr) -> Bachelor(120cr) -> Master(150cr) -> Doctorate(180cr)
- [x] GPA framework implemented: A+(4.0) through F(0.0), 11 letter grades
- [x] Credits-earned computation implemented
- [x] Degree eligibility logic implemented (`eligible_degrees` with GPA/credit thresholds)
- [x] Grades page scaffolded (`pages/06_Grades.py`) with transcript display and degree progress
- [x] Transcript CSV and JSON download implemented in Grades page
- [ ] Verify transcript export correctness against real assignment submissions
- [ ] Add term/semester records and transcript term grouping
- [ ] Add assignment weighting per course/module
- [ ] Add late policy behavior when deadlines mode is enabled
- [ ] Add enrollment date tracking and time-to-degree calculation
- [ ] Add assignment generation and other class material to schema capabilities

## 3. Curriculum and Library Experience
- [x] Library page built (`pages/01_Library.py`)
- [x] Bulk curriculum JSON import UI built
- [x] Course/module/lecture browsing UI built
- [x] LLM schema + guide created (`schemas/course_schema.json`, `schemas/SCHEMA_GUIDE.md`)
- [ ] Add JSON schema validation feedback with clear error line hints
- [ ] Add "repair malformed JSON" helper flow in Professor AI
- [x] Add import dry-run mode (validate without writing DB)
- [x] Course deletion with confirmation exists in Library page
- [ ] Add cascade behavior warning before delete (show count of modules/lectures)

## 4. Lecture Studio and Media Workflow
- [x] Lecture Studio page scaffolded (`pages/02_Lecture_Studio.py`)
- [x] Scene chunk export path scaffolded
- [x] Full lecture render controls scaffolded (fps/width/height/suffix kwargs)
- [x] Timeline Editor page scaffolded (`pages/04_Timeline_Editor.py`)
- [x] Batch Render page scaffolded (`pages/05_Batch_Render.py`)
- [x] Animated video engine rebuilt: particles, typewriter text, waveform, progress bar, pulsing border
- [x] Audio-first pipeline: TTS duration drives video length (no more static/silent frames)
- [x] First render test passed: 40s, 960x540, 15fps, audio synced, 2.22 MB
- [ ] Verify render output files are playable in default Windows player
- [ ] Verify A/V sync on 3+ representative lectures
- [x] Add render retry logic for per-scene failures
- [x] Add render quality profiles (draft, balanced, final)
- [x] Add run summary report per batch render session

## 5. AI Professor and LLM Providers
- [x] Professor UI scaffolded (`pages/03_Professor_AI.py`) with chat, quiz, rabbit hole, grade, curriculum
- [x] Multi-provider config page scaffolded (`pages/08_Settings.py`)
- [x] Local model path included (Ollama / LM Studio)
- [x] Commercial provider path included (OpenAI, Anthropic, Groq, Mistral, Together, HuggingFace, GitHub Models)
- [x] Cohere provider added (10 providers total)
- [x] Professor has 15 capabilities (ask, stream, curriculum, quiz, homework, study_guide, grade_essay, grade_code, oral_exam, concept_map, expand_narration, suggest_next_topics, research_rabbit_hole, enhance_video_prompts)
- [x] Streaming chat method added (`professor.stream()`)
- [x] Hardware check utility exists (`check_hardware()` with RAM/VRAM/CPU)
- [x] Ollama model pull utility in Settings page
- [x] Validate each provider with a real minimal prompt-response smoke test
- [x] Normalize provider errors into friendly user-facing messages
- [x] Add model capability matrix (chat, long-context, fast/cheap, coding)
- [x] Add token and cost telemetry per interaction (where available)

## 6. Audio Quality and Learning Audio
- [x] Neural TTS path included (`edge-tts` with Microsoft Neural voices)
- [x] Fallback TTS path included (`pyttsx3`)
- [x] Binaural preset controls scaffolded (alpha, theta, gamma, delta, beta)
- [x] Procedural SFX generation integrated (pure math sine synthesis)
- [x] Ambient pad generation (additive synthesis with harmonic series)
- [x] `generate_binaural_wav()` tested and verified (176,444 bytes for 1s @ 200Hz base)
- [ ] Verify per-voice narration quality and speed controls across lectures
- [ ] Add audio loudness normalization target for exported videos
- [ ] Add optional "study music only" and "narration only" output modes

## 7. Gamification and Dungeon Theme
- [x] Theme system implemented (`ui/theme.py`) with full dungeon-academic CSS
- [x] Color palette: obsidian bg, arcane cyan, gold, crimson, success green
- [x] XP event model implemented with typed events (video, quiz, assignment, etc.)
- [x] 10 dungeon levels: Seeker -> Initiate -> Acolyte -> Scholar -> Adept -> Mage -> Archmage -> Sage -> Oracle -> Archon
- [x] Achievements page scaffolded (`pages/07_Achievements.py`)
- [x] `achievement_card()` supports both dict and positional args
- [x] Procedural ASCII art headers (no external assets, no emojis)
- [x] Add deterministic unlock rules audit (every achievement has a trigger)
- [ ] Add level-up celebration flow for first-time level transitions
- [ ] Add weekly quest loop (optional toggle)
- [ ] Add XP decay prevention (activity streak bonus)

## 8. Setup, Launch, and Ops
- [x] `setup.bat` exists (creates venv, installs deps, inits DB)
- [x] `start.bat` exists (activates venv, launches Streamlit)
- [x] One-click launcher exists (`DOUBLE_CLICK_SETUP_AND_START.bat`)
- [x] Removed broken ffmpeg installer dependency from bat scripts
- [x] `requirements.txt` exists with all 14 packages pinned
- [x] README.md exists
- [ ] Confirm setup is idempotent across clean and existing environments
- [ ] Add explicit dependency check output after setup
- [ ] Add troubleshooting section in README for common Windows issues
- [ ] Verify all pinned versions install cleanly on fresh Python 3.9+

## 9. Release Readiness Gate
- [x] All 11 pages compile without errors (verified, including Help and LLM Setup)
- [x] All core module imports succeed (verified, including help_registry and app_docs)
- [x] First end-to-end render + playback validated (1 lecture)
- [ ] Minimum 3-lecture render and playback pass
- [ ] Curriculum import/export roundtrip pass
- [ ] Professor chat, quiz, grading, curriculum generation pass (happy path)
- [ ] Deadlines mode on/off behavior validated
- [ ] Transcript CSV/JSON validated
- [ ] No blocker errors in terminal during 30-minute exploratory run
- [x] Streamlit app launches and all 11 sidebar pages are reachable

## 10. Near-Term Execution Priority (Recommended)
- [x] P0: Stabilize backend/page function contracts and eliminate runtime mismatch (DONE)
- [x] P0: Fix video_engine.py compilation blocker (DONE)
- [x] P0: First end-to-end render + playback test passed (40s video, A/V synced)
- [x] P0: Streamlit runtime launch verified (health endpoint OK, dashboard renders)
- [x] P1: Harden provider setup UX and test at least 1 local + 1 cloud provider
- [x] P1: Add import validation + dry-run support
- [ ] P2: Expand grading weight/term support and transcript fidelity
- [x] P2: Diagnostics page added (`pages/09_Diagnostics.py`)
- [x] P1: Comprehensive help system with interconnected navigation
- [x] P1: LLM Setup Wizard page (`pages/11_LLM_Setup.py`) with all 10 providers
- [x] P1: Help page (`pages/10_Help.py`) with 32 entries and query-param navigation
- [x] P1: Professor AI can explain app features via App Guide tab
- [x] P1: [?] help buttons wired into all 10 pages at key sections
- [ ] P1: LLM setup wizard with real credential walkthroughs
- [ ] P2: Professor AI backend reader (explain app usage without exposing code)
