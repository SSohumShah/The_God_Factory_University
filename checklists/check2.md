# AI University LLM + Backend Integration Checklist (Engineering Contract)

This checklist defines what must be true for the LLM/tool stack to support the university app reliably.
Cross-reference: [check1.md](check1.md) covers the product roadmap and delivery milestones.

## A. Contract Integrity (Pages <-> Backend)
- [x] Compatibility shims added to `database.py` for all page-consumed functions
- [x] All 8 pages compile without syntax/import errors (py_compile verified)
- [x] All 6 core modules import cleanly (importlib verified)
- [x] `from __future__ import annotations` added to `database.py` for Python 3.9 compatibility
- [ ] Create and maintain a single source-of-truth API contract doc for:
  - `core.database`
  - `llm.professor`
  - `llm.providers`
  - `media.video_engine`
  - `media.audio_engine`
  - `ui.theme`
- [x] Add a contract test that imports every page module and validates all referenced symbols exist
- [ ] Ban silent alias drift: if compatibility aliases are added, document and deprecate with timeline
- [ ] Enforce type hints for all public functions consumed by pages

## B. LLM Provider Matrix
- [x] Provider abstraction exists (`llm/providers.py` with `LLMConfig`, `chat()`, `simple_complete()`)
- [x] Local providers included (Ollama, LM Studio)
- [x] Cloud providers included (OpenAI, Anthropic, Groq, Mistral, Together, HuggingFace, GitHub Models, Cohere)
- [x] Hardware check utility (`check_hardware()` with GPU/RAM/CPU detection)
- [x] Provider config from settings helper (`cfg_from_settings()`)
- [x] PROVIDER_CATALOGUE dict with models, base URLs, setup hints for all 10 providers
- [ ] Add provider health-check endpoint/function (connectivity + auth + model list)
- [x] Add standardized error mapping (`auth_error`, `rate_limit`, `network`, `bad_model`, `provider_down`)
- [x] Add provider capability map (streaming, context size, json-mode, cost metadata)
- [x] Add provider fallback policy (ordered fallback with user opt-in)

## C. Professor Agent Reliability
- [x] Core professor class exists (`llm/professor.py` with 15 capabilities)
- [x] Prompted curriculum/quiz/grading/homework/study_guide flows exist
- [x] Streaming chat method added (`stream()`)
- [x] Constructor accepts configurable `session_id`
- [x] Chat history persistence via `append_chat()` / `get_chat()` in DB
- [ ] Ensure all Professor methods return a normalized structure:
  - `raw_text`
  - `parsed_json` (nullable)
  - `warnings`
  - `provider_used`
- [ ] Add JSON parse hardening with repair attempts for model responses
- [ ] Add guardrails for overlong outputs and missing required fields
- [ ] Add chat history truncation policy and token budgeting

## D. Media Engine Contract
- [x] Video engine exists with MoviePy pipeline (`media/video_engine.py`)
- [x] Audio engine exists with TTS + procedural audio (`media/audio_engine.py`)
- [x] `video_engine.py` compile/runtime integrity fixed (4 duplicate blocks removed, compiles clean)
- [x] Animated frame renderer: particles, typewriter, waveform, progress bar, pulsing border, timers
- [x] Audio-first pipeline: TTS duration measured first, video matched to it
- [x] Scene-level clip builder with TTS + ambient + binaural mix
- [x] Timeline editor support (`reorder_and_render`)
- [x] Batch render with threaded execution and progress callback
- [x] Render output generation verified (MP4 with H.264 + AAC, 960x540, 15fps)
- [ ] Add deterministic render smoke test (`tests/smoke/test_render_minimal.py`)
- [ ] Add output validation checks:
  - video duration > 0
  - audio stream present
  - resolution expected
  - playable with ffprobe/moviepy
- [x] Add scene-level error isolation (failed scene should not crash whole batch)

## E. Audio Quality Controls
- [x] Voice selection settings exist (edge-tts voice ID, rate, pitch)
- [x] Binaural presets exist (gamma_40hz, beta_18hz, alpha_10hz, theta_6hz with base/beat freq)
- [x] Ambient pad generation (harmonic additive synthesis with root + maj3rd + 5th + octave)
- [x] `generate_binaural_wav()` verified (correct output size)
- [x] SFX presets exist (8 types: click, success, unlock, error, xp_gain, level_up, page_turn, collect)
- [x] Audio mixing pipeline (`mix_audio_files` loops ambient if shorter)
- [ ] Add loudness normalization target (LUFS)
- [ ] Add clipping detection and auto gain reduction
- [ ] Add narration intelligibility profile for lecture speech

## F. Data and Schema Safety
- [x] SQLite schema exists (WAL mode, foreign keys, thread-safe context manager)
- [x] Bulk import exists (`bulk_import_json` returns tuple[int, list[str]])
- [x] JSON schema template created (`schemas/course_schema.json`)
- [x] Schema guide for LLM curriculum generation (`schemas/SCHEMA_GUIDE.md`)
- [x] Settings table with 13 default settings seeded on init
- [x] Chat history persistence (`append_chat`, `get_chat`)
- [x] LLM generated content tracking (`save_llm_generated`, `get_llm_generated`, `mark_imported`)
- [x] Achievement seed data (17 achievement definitions)
- [x] Add JSON Schema validation on import path (jsonschema library)
- [x] Add transaction rollback for partial import failures
- [x] Add import report artifact (counts, warnings, errors)
- [x] Add migration version table and migration runner

## G. Testing and CI Gates
- [x] Add baseline tests:
  - DB init and CRUD
  - curriculum import
  - professor prompt calls (mocked)
  - audio generation
  - video minimal render
- [x] Page compile test verified for all 9 files in `pages/` (including 09_Diagnostics)
- [x] All 6 core modules import verified (database, providers, professor, audio, video, theme)
- [ ] Add regression test for known bug classes:
  - signature mismatch
  - missing optional settings
  - invalid JSON from LLM
  - non-playable MP4 output
  - Python 3.9 type annotation compatibility
- [ ] Define "green build" gate before merging feature work

## H. Operations and Observability
- [x] Add structured logs for render jobs, provider calls, and import operations
- [ ] Add error IDs surfaced to UI for quick support triage
- [x] Diagnostics page implemented (`pages/09_Diagnostics.py`):
  - Python/env details (version, platform, cwd)
  - Dependency versions (14 packages)
  - DB stats (courses, modules, lectures, assignments, GPA, credits, XP total)
  - Provider connectivity checks (with live test button)
  - FFmpeg binary path verification
  - TTS engine status (with live test button)
  - Module compile health check (17 files)
  - Raw settings viewer (API keys masked)

## I. Security and Secrets
- [ ] Store API keys securely (avoid plain text in DB where possible)
- [x] Never log raw secrets
- [ ] Add provider key presence checks before enabling provider actions
- [ ] Add explicit warning banner when using paid providers
- [x] Sanitize LLM outputs before rendering in Streamlit (prevent injection via st.markdown)

## J. Milestone Exit Criteria

### Milestone 1: Stable Alpha
- [x] All 11 pages compile and core modules import (11 pages + 8 modules)
- [x] Core import/render/grade flows complete without crash (1-lecture pass)
- [x] Streamlit app launches cleanly and all sidebar pages reachable
- [ ] 3-lecture end-to-end pass (import -> render -> play -> grade)

### Milestone 2: University Beta
- [ ] Degree + grading + deadlines + achievements validated end-to-end
- [ ] Batch render overnight pass with recovery from one forced failure
- [ ] 2 provider backends validated (1 local, 1 cloud)
- [ ] XP/level/achievement flow verified across 10+ interactions

### Milestone 3: Public-Ready Build
- [ ] Full smoke matrix green on fresh Windows setup (Python 3.9+)
- [ ] Setup/start scripts verified from clean machine profile
- [ ] README and troubleshooting docs aligned with real behavior
- [ ] No external dependencies required (all bundled or auto-installed)

## K. Immediate Engineering Priorities (This Repo)
- [x] P0: Resolve `media/video_engine.py` indentation/runtime issues (DONE)
- [x] P0: Run import check for `app.py` and every file in `pages/` (DONE - all compile)
- [x] P0: End-to-end workflow verified: import -> render -> progress -> grade -> GPA (23/24 tests pass)
- [x] P0: Streamlit runtime launch verified (health endpoint OK, empty DB cold start clean)
- [ ] P1: Add automated contract test to prevent future page/backend drift
- [x] P1: Diagnostics page created (`pages/09_Diagnostics.py`): env, deps, DB stats, LLM test, TTS test, compile check
- [ ] P1: Validate at least 1 LLM provider end-to-end (Ollama recommended for local)
- [x] P1: Comprehensive help system with contextual navigation
- [x] P1: LLM setup wizard with real provider walkthroughs
- [x] P2: Professor AI backend reader (code-aware explanations)
- [x] P1: [?] help buttons wired into all 10 page files
- [x] P1: Help registry with 32 entries across all pages
- [x] P1: App docs module (11 topics) for Professor backend reading
