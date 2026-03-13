# Arcane University: Gap Analysis & Implementation Checklist

Cross-references: [check1.md](check1.md) (product roadmap), [check2.md](check2.md) (engineering contract), [check3.md](check3.md) (academic structure)

This checklist covers every remaining gap between the current working codebase and
the vision of a real, fully functional AI-powered university.

---

## Phase A: Comprehensive Interconnected Help System
> Everything in the app can be clicked and navigate to the help section that describes it.

### A.1 Help Infrastructure
- [x] Create `pages/10_Help.py` — master help page with anchored sections for every feature
- [x] Create `core/help_registry.py` — central dict mapping (page, element) -> help text + anchor
- [x] Register every sidebar page with a help entry (Dashboard, Library, Lecture Studio, Professor AI, Timeline Editor, Batch Render, Grades, Achievements, Settings, Diagnostics)
- [x] Add `help_button(topic_key)` utility in `ui/theme.py` — renders a small [?] link next to any widget
- [x] Wire `help_button` to navigate to `10_Help.py#anchor` for contextual help
- [x] Add `st.query_params` reading in Help page to auto-scroll to the requested section

### A.2 Help Content — Dashboard
- [x] Help entry: "What is the Dashboard?" — purpose, stat cards, quick start workflow
- [x] Help entry: "System Health" — what each probe checks, what failures mean
- [x] Help entry: "XP and Levels" — how XP is earned, level thresholds, rank titles
- [ ] Help entry: "First Launch" — what happens on first run, auto-import from notes.txt

### A.3 Help Content — Library
- [x] Help entry: "Importing Courses" — JSON formats accepted, single/array/multiline, schema reference
- [x] Help entry: "Course JSON Schema" — full field-by-field explanation of `course_schema.json`
- [x] Help entry: "Browsing Courses" — modules, lectures, progress badges, expanding cards
- [x] Help entry: "Deleting Courses" — what gets removed, cascade behavior

### A.4 Help Content — Lecture Studio
- [x] Help entry: "Playing Lectures" — video player, progress tracking, XP awards
- [x] Help entry: "Rendering a Lecture" — what happens during render, FPS/resolution, output location
- [x] Help entry: "Scene Chunks" — exporting individual scenes, chunk-by-scene mode
- [x] Help entry: "Assignment Submission" — how scoring works, grade scale, feedback

### A.5 Help Content — Professor AI
- [x] Help entry: "Chat with Professor" — how to ask questions, streaming, chat history
- [x] Help entry: "Generate Curriculum" — how LLM creates course JSON, editing before import
- [x] Help entry: "Grade Work" — essay and code grading, rubric, score interpretation
- [x] Help entry: "Create Quiz" — auto-quiz generation, question types, answer review
- [x] Help entry: "Research Rabbit Hole" — deep exploration, open problems, related topics

### A.6 Help Content — Timeline Editor
- [x] Help entry: "Reordering Scenes" — drag/move, duration overrides, re-render
- [x] Help entry: "Exporting Timeline" — modified JSON export

### A.7 Help Content — Batch Render
- [x] Help entry: "Queue Management" — selecting lectures, starting batch render
- [ ] Help entry: "Render Settings" — FPS, resolution, output format
- [ ] Help entry: "Prompt Pack Export" — Runway/Pika/ComfyUI formats, external tool integration

### A.8 Help Content — Grades & Transcript
- [x] Help entry: "GPA Calculation" — formula, grade scale table, honors thresholds
- [x] Help entry: "Degree Eligibility" — credit + GPA gates for each degree tier
- [x] Help entry: "Transcript Download" — CSV vs JSON, what fields are included
- [ ] Help entry: "Assignment Records" — score, grade, feedback, deadline status

### A.9 Help Content — Achievements
- [x] Help entry: "Achievement System" — categories, unlock triggers, XP rewards
- [x] Help entry: "Level System" — 10 tiers, XP thresholds, rank names and symbols
- [ ] Help entry: "XP Events" — what actions earn XP, event types

### A.10 Help Content — Settings
- [x] Help entry: "Voice Settings" — edge-tts voices, rate/pitch sliders, preview
- [x] Help entry: "Binaural Beats" — what they are, preset descriptions, science references
- [x] Help entry: "LLM Provider" — overview of all 10 providers, when to use each
- [x] Help entry: "Video Settings" — FPS, resolution, render backend options
- [x] Help entry: "Deadline System" — what happens when enabled, late policy

### A.11 Help Content — Diagnostics
- [x] Help entry: "Diagnostics Page" — what each section tests, how to read results
- [x] Help entry: "Compile Check" — what it validates, how to fix failures
- [x] Help entry: "LLM Test" — what the connectivity test does, interpreting results

### A.12 Help Navigation Integration
- [x] Add [?] help buttons to every Settings section (voice, binaural, LLM, video, deadlines)
- [x] Add [?] help buttons to Library import area, course cards
- [x] Add [?] help buttons to Professor AI tabs
- [x] Add [?] help buttons to Grades GPA display, degree display
- [x] Add [?] help buttons to Achievements level badge, XP bar
- [x] Add [?] help buttons to Lecture Studio player, render controls
- [x] Add [?] help buttons to Dashboard stat cards, health panel
- [x] Add help link to sidebar (always visible)
- [x] Test every help button navigates to correct anchor

---

## Phase B: Professor AI Backend Reader
> Professor can read backend logic and explain how to use the app in depth without giving away code secrets.

### B.1 Backend Documentation Generator
- [x] Create `core/app_docs.py` — module that generates structured documentation from the codebase
- [x] Document every public function in `core/database.py` — name, purpose, parameters, return values (NO source code)
- [x] Document every public function in `llm/providers.py` — provider names, capabilities, config options
- [x] Document every method in `llm/professor.py` — name, purpose, input/output descriptions
- [x] Document every public function in `media/audio_engine.py` — voice list, presets, capabilities
- [x] Document every public function in `media/video_engine.py` — render pipeline, output specs
- [x] Document every component in `ui/theme.py` — available widgets, color palette, styling
- [x] Document database schema — all tables, columns, relationships (NO raw SQL)
- [x] Document settings — all keys, value types, defaults, effects
- [x] Document degree system — tracks, credit gates, GPA requirements
- [x] Document XP/level system — events, thresholds, achievements

### B.2 Professor System Prompt Enhancement
- [x] Add `explain_app(topic)` method to Professor class — generates contextual app usage explanation
- [x] Create "App Guide" system prompt section that injects relevant docs into Professor context
- [x] Add safety filter: strip file paths, function signatures, internal implementation details
- [x] Allow Professor to answer "How do I..." questions about the app (import, render, grade, etc.)
- [x] Allow Professor to explain settings effects ("What does binaural gamma mode do?")
- [x] Allow Professor to recommend workflow sequences ("How should I use this app to study X?")

### B.3 Professor AI "About This App" Tab
- [x] Add 6th tab to `pages/03_Professor_AI.py` — "App Guide"
- [x] In App Guide tab: user types question about any app feature, professor explains using docs
- [x] Include quick-link buttons: "How do I import a course?", "How does grading work?", "What LLM providers are available?"
- [x] Include "Explain this setting" dropdown — pick any setting key, get professor explanation
- [x] Ensure professor NEVER outputs raw source code, SQL queries, or file paths

---

## Phase C: Real LLM Provider Setup Wizard
> Full walkthroughs for every provider, click-to-setup UI, credential validation, local model capability detection.

### C.1 Provider Setup Wizard Page
- [x] Create `pages/11_LLM_Setup.py` -- dedicated guided LLM setup wizard
- [x] Add wizard step navigation (step 1: choose type -> step 2: choose provider -> step 3: configure -> step 4: test)
- [x] Add "Local vs Cloud" decision helper with pros/cons comparison table
- [x] Add hardware requirement display for local models (RAM, VRAM, disk)
- [x] Add cost comparison table for cloud providers (free tier limits, per-token pricing)

### C.2 Ollama Setup Walkthrough (Local, Free)
- [x] Step-by-step: Download from ollama.com (Windows, Mac, Linux links)
- [x] Step-by-step: Verify installation -- run `ollama --version` check
- [x] Auto-detect: Check if Ollama service is running (HTTP check to localhost:11434)
- [x] Model browser: List available models (ollama list), show sizes and capabilities
- [x] One-click pull: Select model from dropdown, pull with progress bar
- [x] Hardware advisor: Based on RAM/VRAM, recommend which models will run well
- [x] Test button: Send a test prompt and display response
- [x] Troubleshooting: Common issues (port in use, firewall, service not started)
- [x] Models to show: llama3.2 (3B, lightweight), llama3.1 (8B, balanced), codellama (coding), phi3 (small/fast), mistral (general), gemma2 (Google), qwen2.5-coder (coding)

### C.3 LM Studio Setup Walkthrough (Local, Free)
- [x] Step-by-step: Download from lmstudio.ai (Windows installer)
- [x] Step-by-step: Launch LM Studio, browse/download a model from the Discover tab
- [x] Step-by-step: Load model, click "Start Server" in the Local Server tab
- [x] Auto-detect: Check if LM Studio server is running (HTTP check to localhost:1234)
- [x] Model note: LM Studio uses GGUF format models from HuggingFace
- [x] RAM guide: 4GB RAM -> tiny models, 8GB -> 7B models, 16GB -> 13B models, 32GB -> 30B+
- [x] Test button: Send a test prompt and display response
- [x] Troubleshooting: Server not responding, model not loaded, out of memory

### C.4 OpenAI Setup Walkthrough (Cloud, Paid)
- [x] Step-by-step: Create account at platform.openai.com
- [x] Step-by-step: Navigate to API Keys section, create new secret key
- [x] Step-by-step: Add billing -- payment method required before API works
- [x] API key input: Paste key, validate format (starts with `sk-`)
- [x] Base URL: `https://api.openai.com/v1` (pre-filled, allow override for Azure)
- [x] Model selection: gpt-4o (best quality), gpt-4o-mini (fast/cheap), gpt-4-turbo
- [x] Cost info: gpt-4o ~$2.50/$10 per 1M tokens (input/output), gpt-4o-mini ~$0.15/$0.60
- [x] Rate limits: Tier 1 (new): 500 RPM, 30K TPM; scales with usage
- [x] Test button: Send a test prompt and display response + token count
- [x] Troubleshooting: Invalid key, billing not set up, rate limit exceeded

### C.5 Anthropic (Claude) Setup Walkthrough (Cloud, Paid)
- [x] Step-by-step: Create account at console.anthropic.com
- [x] Step-by-step: Navigate to API Keys, create new key
- [x] Step-by-step: Add billing -- prepaid credits or credit card
- [x] API key input: Paste key, validate format
- [x] Note: Anthropic uses its OWN SDK (not OpenAI-compatible) -- handled internally
- [x] Model selection: claude-sonnet-4-20250514 (balanced), claude-3-haiku (fast/cheap), claude-opus-4-20250514 (best)
- [x] Cost info: Sonnet ~$3/$15 per 1M tokens, Haiku ~$0.25/$1.25
- [x] Context window: 200K tokens for all Claude 3.5+ models
- [x] Test button: Send a test prompt and display response
- [x] Troubleshooting: Authentication errors, credit exhaustion, region restrictions

### C.6 Groq Setup Walkthrough (Cloud, Free Tier)
- [x] Step-by-step: Create account at console.groq.com (Google/GitHub auth supported)
- [x] Step-by-step: Navigate to API Keys, create key
- [x] Note: FREE tier available -- generous rate limits without payment
- [x] API key input: Paste key, validate format (starts with `gsk_`)
- [x] Base URL: `https://api.groq.com/openai/v1` (pre-filled)
- [x] Model selection: llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768, gemma2-9b-it
- [x] Cost info: Free tier with rate limits (30 RPM, ~500K tokens/day on free)
- [x] Speed note: Groq is extremely fast due to custom LPU hardware (~500 tokens/sec)
- [x] Test button: Send a test prompt and display response + speed measurement
- [x] Troubleshooting: Rate limit hit, model not available, key invalid

### C.7 GitHub Models Setup Walkthrough (Cloud, Free with PAT)
- [x] Step-by-step: Log into GitHub, go to Settings > Developer Settings > Personal Access Tokens
- [x] Step-by-step: Generate new token (classic) -- NO special scopes needed
- [x] Note: FREE -- uses GitHub Models marketplace (models.inference.ai.azure.com)
- [x] API key input: Paste PAT, validate format (starts with `ghp_`)
- [x] Base URL: `https://models.inference.ai.azure.com` (pre-filled)
- [x] Model selection: gpt-4o, gpt-4o-mini, meta-llama-3.1-70b-instruct, mistral-large, phi-3-medium
- [x] Cost info: Free during preview, rate-limited per model
- [x] Test button: Send a test prompt and display response
- [x] Troubleshooting: PAT expired, model quota exceeded

### C.8 Mistral AI Setup Walkthrough (Cloud, Free Tier Available)
- [x] Step-by-step: Create account at console.mistral.ai
- [x] Step-by-step: Navigate to API Keys section, create new key
- [x] Step-by-step: Experiment plan is free; Scale plan for production
- [x] API key input: Paste key, validate format
- [x] Base URL: `https://api.mistral.ai/v1` (pre-filled)
- [x] Model selection: mistral-large-latest (best), mistral-small-latest (fast/cheap), codestral-latest (coding)
- [x] Cost info: Mistral Small ~$0.1/$0.3 per 1M tokens, Large ~$2/$6
- [x] Context window: 32K-128K depending on model
- [x] Test button: Send a test prompt and display response
- [x] Troubleshooting: Key invalid, billing not set up, model not available in region

### C.9 Together AI Setup Walkthrough (Cloud, Free Tier)
- [x] Step-by-step: Create account at api.together.xyz
- [x] Step-by-step: API key visible on dashboard after signup
- [x] Note: Free tier with $5 credits on signup
- [x] API key input: Paste key, validate format
- [x] Base URL: `https://api.together.xyz/v1` (pre-filled)
- [x] Model selection: meta-llama/Llama-3.1-70B-Instruct-Turbo, mistralai/Mixtral-8x7B, Qwen/Qwen2.5-72B
- [x] Cost info: Varies by model; Llama-3.1-8B ~$0.18/1M tokens
- [x] Speed note: Together AI runs open models on fast GPU clusters
- [x] Test button: Send a test prompt and display response
- [x] Troubleshooting: Credit exhaustion, model not found, network errors

### C.10 HuggingFace Inference Setup Walkthrough (Cloud, Free Tier)
- [x] Step-by-step: Create account at huggingface.co
- [x] Step-by-step: Go to Settings > Access Tokens, create new token
- [x] Note: Free tier for many models; Pro subscription for higher limits
- [x] API key input: Paste token, validate format (starts with `hf_`)
- [x] Base URL: `https://api-inference.huggingface.co/v1` (pre-filled)
- [x] Model selection: meta-llama/Llama-3.1-8B-Instruct, mistralai/Mistral-7B-Instruct-v0.3
- [x] Cost info: Free for Inference API (rate-limited), Pro for dedicated endpoints
- [x] Note: Model availability depends on HuggingFace hosting; not all models available
- [x] Test button: Send a test prompt and display response
- [x] Troubleshooting: Model loading (cold start delays), token invalid, rate limits

### C.11 Cohere Setup Walkthrough (Cloud, Free Tier)
- [x] Step-by-step: Create account at dashboard.cohere.com
- [x] Step-by-step: Navigate to API Keys, copy key
- [x] Note: Free trial tier available
- [x] API key input: Paste key, validate format
- [x] Model selection: command-r-plus (best), command-r (fast)
- [x] Test button: Send a test prompt and display response

### C.12 Local Model Capability Detection
- [x] Auto-scan: Detect Ollama running -> list installed models with sizes
- [x] Auto-scan: Detect LM Studio running -> query loaded model
- [x] Hardware profiler: RAM, VRAM, CPU cores -> capability tier (tiny/small/medium/large/xl)
- [x] Model recommender: Based on hardware tier, suggest best local models
- [x] VRAM calculator: Show estimated VRAM usage per model size (3B->2GB, 7B->5GB, 13B->9GB, 30B->20GB, 70B->40GB)
- [x] Disk space check: Show estimated download sizes for recommended models
- [x] Running model health: Ping active local model, show response time

### C.13 Provider Validation & Testing
- [x] Universal test function: Send "Hello, respond with one sentence" to any configured provider
- [x] Response time measurement: Show latency in milliseconds
- [x] Token counting: Show input/output tokens used in test
- [x] Error classification: auth_error, rate_limit, network, bad_model, timeout -> friendly message
- [x] Provider status badge: green (working), yellow (slow), red (error) -> persisted
- [ ] Auto-test on save: When user saves provider settings, auto-run connectivity test

### C.14 Provider Comparison Dashboard
- [x] Side-by-side table: all 10 providers, status, speed, cost tier, context window
- [x] Recommendation engine: Based on user goals (free, fast, best quality, coding, long context)
- [x] "Best for you" card: Single recommendation based on hardware + budget + use case
- [x] One-click switch: Change active provider from comparison view

---

## Phase D: Academic Infrastructure Gaps (Bridge to check3.md)
> Gaps between the current 5-degree system and the full K-Doctorate academic structure in check3.

### D.1 Grade Level System
- [ ] Extend database schema: add `grade_level` table (K, 1-12, Freshman, Sophomore, Junior, Senior, Graduate, Doctoral)
- [ ] Add student grade level to profile/settings
- [ ] Create grade-level-appropriate content filtering
- [ ] Implement grade level progression logic
- [ ] Add grade level display in student profile

### D.2 Subject Taxonomy
- [ ] Create `subjects` table — hierarchical (domain > field > subfield > topic)
- [ ] Seed initial subject taxonomy (minimum: Math, Science, English, History, CS, Arts)
- [ ] Map existing courses to subjects
- [ ] Add subject browsing UI to Library
- [ ] Add subject-based course recommendations

### D.3 Placement Testing Foundation
- [ ] Create `placement_tests` table (test_id, subject, difficulty_range, created_at)
- [ ] Create `placement_questions` table (question_id, test_id, question_text, options, correct_answer, difficulty)
- [ ] Create `placement_results` table (result_id, student, test_id, score, recommended_level, taken_at)
- [ ] Implement basic placement test engine using Professor AI to generate questions
- [ ] Create placement test UI page (`pages/12_Placement.py`)
- [ ] Implement adaptive difficulty: increase/decrease based on performance
- [ ] Generate placement recommendation based on results

### D.4 Standardized Test Prep Foundation
- [ ] Create `test_prep` table (prep_id, test_name, section, question_bank_json)
- [ ] Create basic GED practice module (math + reading as first targets)
- [ ] Create basic SAT practice module (math + reading as first targets)
- [ ] Implement timed test mode (countdown, section timing)
- [ ] Implement score calculation with percentile estimation
- [ ] Add test prep UI page (`pages/13_Test_Prep.py`)
- [ ] Use Professor AI to generate practice questions on demand

### D.5 Expanded Curriculum Structure
- [ ] Add `programs` table — defines academic programs (CS Major, MBA, etc.)
- [ ] Add `program_requirements` table — courses/credits needed per program
- [ ] Add `enrollments` table — student enrollment in programs
- [ ] Create program browsing page or section in Library
- [ ] Implement program progress tracking (required vs completed courses)
- [ ] Add program completion / certificate generation

### D.6 Student Profile Enhancement
- [ ] Add student profile page (`pages/14_Profile.py`)
- [ ] Store educational background (self-reported)
- [ ] Store learning preferences (visual, auditory, reading, kinesthetic)
- [ ] Track session history (app opens, time spent, features used)
- [x] Create study streak tracking (consecutive days with activity)
- [ ] Add basic performance analytics dashboard (grades over time, XP over time)

### D.7 Statistics & Analytics
- [ ] Add `activity_log` table (event_type, timestamp, duration, metadata)
- [ ] Track lecture views, quiz attempts, assignment submissions, professor queries
- [ ] Create statistics dashboard (`pages/15_Statistics.py`)
- [ ] Display: total study hours, lectures completed, assignments submitted, quizzes taken
- [ ] Display: daily/weekly activity heatmap
- [ ] Display: grade trend chart (GPA over time)
- [ ] Display: subject performance breakdown

---

## Phase E: Core App Quality Gaps (from check1 + check2 remaining items)
> Items from check1 and check2 that are still incomplete.

### E.1 Import & Schema Validation
- [x] Add `jsonschema` to requirements.txt
- [x] Validate imported JSON against `schemas/course_validation_schema.json` before writing to DB
- [x] Surface clear error messages with line hints on validation failure
- [x] Add "repair malformed JSON" helper in Professor AI
- [x] Add import dry-run mode (validate without writing DB)
- [x] Add import report artifact (counts, warnings, errors written to log)

### E.2 Render Quality & Reliability
- [ ] Verify render output files are playable in default Windows player
- [ ] Verify A/V sync on 3+ representative lectures
- [x] Add render retry logic for per-scene failures
- [x] Add render quality profiles (Draft, Balanced, High Quality, Final, Custom)
- [x] Add batch render summary report (time, sizes, errors)
- [x] Add scene-level error isolation (failed scene should not crash whole batch)

### E.3 Provider Error Handling
- [x] Normalize provider errors into user-facing messages
- [x] Add standardized error map (auth_error, rate_limit, network, bad_model, timeout, provider_down)
- [x] Add provider capability map (streaming yes/no, context size, json-mode support, cost per token)
- [x] Add provider fallback policy (try provider A, if fail try provider B)
- [x] Add token and cost telemetry per interaction (where applicable)

### E.4 Audio Enhancement
- [ ] Verify per-voice narration quality and speed controls across lectures
- [x] Add audio loudness normalization target (LUFS) for exported videos
- [x] Add optional "study music only" and "narration only" output modes
- [x] Add clipping detection and auto gain reduction

### E.5 Gamification Polish
- [x] Audit all 17 achievements — ensure each has a working unlock trigger in code
- [x] Add level-up celebration flow for first-time level transitions
- [x] Add weekly quest loop (optional toggle in Settings)
- [x] Add XP decay prevention (activity streak bonus)

### E.6 Grading & Transcript Expansion
- [x] Add term/semester records and transcript term grouping
- [x] Add assignment weighting per course/module
- [x] Add late policy behavior when deadlines mode is enabled
- [x] Add enrollment date tracking and time-to-degree calculation
- [x] Verify transcript export correctness against real assignment submissions

### E.7 Testing & CI
- [x] Create `tests/` directory with baseline tests: DB CRUD, import, audio gen, minimal render
- [x] Add regression tests for known bug classes (signature mismatch, invalid JSON from LLM)
- [x] Add contract test: import every page module, validate all referenced symbols exist
- [x] Define "green build" gate (all tests pass before feature work)

### E.8 Operations & Security
- [x] Add structured logging for render jobs, provider calls, import operations
- [x] Store API keys encrypted or use environment variables (avoid plain text in DB)
- [x] Never log raw secrets
- [x] Add provider key presence check before enabling provider actions
- [x] Add explicit warning banner when using paid providers
- [x] Sanitize LLM outputs before rendering in Streamlit (prevent injection via st.markdown)
- [x] Add error IDs surfaced to UI for quick support triage

### E.9 Documentation & Setup
- [x] Add troubleshooting section in README for common Windows issues
- [x] Verify setup.bat is idempotent across clean and existing environments
- [x] Add explicit dependency check output after setup
- [x] Create API contract doc for all public modules (database, professor, providers, audio, video, theme)

---

## Phase F: Milestone Exit Criteria

### F.1 Alpha Complete (Current Target)
- [x] All 11 pages compile and core modules import
- [x] 1-lecture end-to-end render/grade pass
- [x] Streamlit launches cleanly with all sidebar pages reachable
- [x] Help system (Phase A) -- core sections implemented, 32 entries, [?] buttons wired
- [x] LLM setup wizard (Phase C) -- all 10 providers with walkthroughs complete
- [ ] 3-lecture end-to-end render/play/grade pass
- [x] Professor backend reader (Phase B) -- explain_app() working with 11 doc topics

### F.2 Beta Complete
- [ ] All 10 providers validated with real connectivity tests
- [x] Help system covers all pages with contextual [?] buttons
- [ ] Placement test foundation working (Phase D.3)
- [ ] Student profile and basic statistics (Phase D.6, D.7)
- [ ] Batch render overnight pass with error recovery
- [ ] Degree + grading + deadlines + achievements validated end-to-end

### F.3 University Ready
- [ ] Full walkthrough wizard for every provider (Phase C.2-C.11)
- [ ] Subject taxonomy and program structure (Phase D.2, D.5)
- [ ] Test prep foundation — GED + SAT (Phase D.4)
- [ ] Grade level system operational (Phase D.1)
- [ ] Full test suite green (Phase E.7)
- [ ] README and troubleshooting docs complete
- [ ] Fresh Windows install verified

### F.4 God Factory (check3.md Integration)
- [ ] Phase 0: Core Academic Architecture — grade levels, subject taxonomy
- [ ] Phase 1: Placement & Aptitude Testing — adaptive engine, prerequisite assessment
- [ ] Phase 2: Standardized Test Prep — GED, SAT, ACT, GRE, GMAT, LSAT, MCAT, Bar, USMLE, NCLEX, CPA
- [ ] Phase 3: Curriculum K-Doctorate — K-5, middle school, high school, undergrad (10 schools, 3+ majors each), masters, doctoral
- [ ] Phase 4: Real-World Hard Problems — unsolved math, physics, CS/AI, biology, social sciences
- [ ] Phase 5: Student Profile & Statistics — activity counters, course stats, cumulative analytics, time-based analytics
- [ ] Phase 6: Behavioral & Aptitude Assessment — learning efficiency, behavioral profiles, cognitive assessment, predictive analytics
- [ ] Phase 7: Implementation Priority — working mechanics first, then secondary/tertiary/future

---

## Implementation Priority Order

1. **Phase A** (Help System) — foundation for discoverability
2. **Phase C.1-C.2** (Setup Wizard + Ollama) — get at least one provider working for new users
3. **Phase B** (Professor Backend Reader) — makes the app self-documenting
4. **Phase C.3-C.11** (Remaining Provider Walkthroughs) — unlock all LLM backends
5. **Phase E** (Core Quality Gaps) — harden import, render, grading, testing
6. **Phase D** (Academic Infrastructure) — bridge to the full university vision
7. **Phase F.4** (God Factory) — the long-term 721-item academic expansion

---

## Legend
- `[ ]` Not started
- `[~]` In progress
- `[x]` Completed
- `[!]` Blocked
- `[?]` Needs research

**Total New Tasks: ~230** | **Completion: ~2%** (milestone F.1 partial items done)
