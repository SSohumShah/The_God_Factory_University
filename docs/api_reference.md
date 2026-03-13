# API Reference — The God Factory University

Public interfaces for all core modules. Internal/private helpers (prefixed with `_`) are omitted.

---

## core.database

Main persistence layer. Re-exports everything from `db_achievements`, `db_grades`, and `db_shims`.

### Constants

| Name | Type | Description |
|------|------|-------------|
| `DB_PATH` | `Path` | Absolute path to `university.db` |
| `LEVELS` | `list[tuple[int, str]]` | XP thresholds and rank titles (Seeker → Archon) |

### Context Manager

| Name | Signature | Description |
|------|-----------|-------------|
| `tx` | `() → Generator[Connection]` | Yields a WAL-mode SQLite connection with auto-commit/rollback |

### Settings

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `init_db` | `()` | `None` | Create tables and seed defaults (idempotent) |
| `get_setting` | `key, default=""` | `str` | Read a setting value |
| `set_setting` | `key, value` | `None` | Insert or replace a setting |

### XP & Levels

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `add_xp` | `amount, description, event_type="general"` | `int` | Award XP with streak bonus; returns new total |
| `get_xp` | | `int` | Current total XP |
| `get_level` | `xp=None` | `(idx, title, in_level, to_next)` | Level info tuple |

### Courses & Curriculum

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `upsert_course` | `course_id, title, description, credits, data, source="imported"` | `None` | Insert/replace course |
| `upsert_module` | `module_id, course_id, title, order_index, data` | `None` | Insert/replace module |
| `upsert_lecture` | `lecture_id, module_id, course_id, title, duration_min, order_index, data` | `None` | Insert/replace lecture |
| `get_all_courses` | | `list[dict]` | All courses ordered by created_at |
| `get_modules` | `course_id` | `list[dict]` | Modules for a course |
| `get_lectures` | `module_id` | `list[dict]` | Lectures for a module |
| `get_lecture` | `lecture_id` | `dict or None` | Single lecture by ID |
| `delete_course` | `course_id` | `None` | Delete course + children |
| `validate_course_json` | `obj` | `list[str]` | Validate against JSON schema |
| `bulk_import_json` | `raw, validate_only=False` | `(count, errors)` | Import JSON/JSONL curriculum |

### Progress

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `get_progress` | `lecture_id` | `dict` | Progress for a lecture |
| `set_progress` | `lecture_id, status, watch_time_s=0, score=None` | `None` | Update progress; awards XP on completion |
| `count_completed` | | `int` | Number of completed lectures |

### Assignments

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `save_assignment` | `assignment_dict` | `None` | Insert/replace assignment (supports weight, term_id) |
| `submit_assignment` | `assignment_id, score, feedback=""` | `None` | Submit score; applies late penalty if enabled |
| `get_assignments` | `course_id=None` | `list[dict]` | All or course-filtered assignments |
| `get_overdue` | `now=None` | `list[dict]` | Unsubmitted past-due assignments |

### Terms & Enrollment

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `upsert_term` | `term_id, title, start_date="", end_date="", order_index=0` | `None` | Insert/replace term |
| `get_terms` | | `list[dict]` | All terms ordered by order_index |
| `get_assignments_by_term` | `term_id` | `list[dict]` | Assignments for a term |
| `get_enrollment_date` | | `str` | Enrollment date (auto-sets today) |
| `time_to_degree_days` | | `int` | Days since enrollment |

### Grades & Degrees

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `compute_gpa` | | `(gpa, count)` | Weighted GPA and graded count |
| `credits_earned` | | `int` | Total credits from completed courses |
| `eligible_degrees` | `gpa=None, credits=None` | `list[str]` | Degree names the student qualifies for |
| `score_to_grade` | `score` | `(letter, points)` | Percentage to letter grade |

### Chat History

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `append_chat` | `session_id, role, content` | `None` | Append chat message |
| `get_chat` | `session_id, limit=50` | `list[dict]` | Recent messages (oldest first) |

### LLM Generated Content

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `get_llm_generated` | `imported=False` | `list[dict]` | LLM-generated content rows |
| `mark_imported` | `row_id` | `None` | Mark row as imported |

### Achievements

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `seed_achievements` | | `None` | Insert achievement defs (idempotent) |
| `unlock_achievement` | `achievement_id` | `bool` | Unlock; returns True if newly unlocked |
| `get_achievements` | | `list[dict]` | All achievements by category |

### Weekly Quests

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `seed_weekly_quests` | | `None` | Create this week's quests (idempotent) |
| `get_active_quests` | | `list[dict]` | Quests for the current week |
| `update_quest_progress` | `quest_prefix, increment=1` | `None` | Advance quest; auto-awards XP at target |

### Shim Aliases

Backward-compatible wrappers — prefer canonical names above.

| Alias | Canonical |
|-------|-----------|
| `save_setting` | `set_setting` |
| `get_all_achievements` | `get_achievements` |
| `get_total_xp` | `get_xp` |
| `save_chat_history` | `append_chat` |
| `get_chat_history` | `get_chat` |
| `get_xp_history(limit)` | XP events (newest last) |
| `get_level_info(xp)` | `get_level` |
| `get_gpa()` | GPA as plain float |
| `save_llm_generated(...)` | Flexible insert wrapper |
| `save_llm_generated_raw(content, type)` | Direct insert; returns row ID |

---

## llm.professor — `Professor` class

AI advisor with 15+ capabilities.

### Constructor

```python
Professor(session_id: str = "default")
```

### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `repair_json` *(static)* | `raw` | `str or None` | Recover valid JSON from malformed LLM output |
| `ask` | `question, stream=False` | `str` | Socratic dialogue; records chat history |
| `stream` | `user_input` | `Generator` | Yield streaming response chunks |
| `generate_curriculum` | `topics, level="undergraduate", lectures_per_module=3` | `str` | Full course JSON; awards 100 XP |
| `generate_quiz` | `lecture_data, num_questions=5` | `str` | Multiple-choice quiz JSON |
| `generate_homework` | `lecture_data` | `str` | Homework assignment JSON |
| `study_guide` | `lecture_data` | `str` | Study guide JSON |
| `grade_essay` | `essay_text, rubric=""` | `str` | Grade essay with feedback JSON |
| `grade_code` | `code_text, task_description=""` | `str` | Review/grade code JSON |
| `expand_narration` | `scene, lecture` | `str` | 60s voiceover script |
| `suggest_next_topics` | `completed_titles` | `str` | 5 topic suggestions JSON |
| `research_rabbit_hole` | `term` | `str` | Deep-dive research JSON |
| `enhance_video_prompts` | `lecture_data` | `str` | Cinematic prompt enhancements |
| `concept_map` | `lecture_data` | `str` | Concept-map JSON (nodes + edges) |
| `oral_exam` | `lecture_data, student_answer, question` | `str` | Socratic oral examination |
| `explain_app` | `question` | `str` | Explain app feature using internal docs |

---

## llm.providers

Universal LLM client supporting 10 providers.

### Constants

| Name | Description |
|------|-------------|
| `PROVIDER_CATALOGUE` | Registry: label, type, base_url, default_models, needs_key |
| `PROVIDER_CAPABILITIES` | Per-provider: streaming, context_window, json_mode, cost rates |

### `LLMConfig` (dataclass)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `str` | `"ollama"` | Provider key |
| `model` | `str` | `"llama3"` | Model name |
| `api_key` | `str` | `""` | API key |
| `base_url` | `str` | `""` | Override base URL |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `max_tokens` | `int` | `4096` | Max output tokens |
| `system_prompt` | `str` | `""` | System prompt |
| `extra` | `dict` | `{}` | Extra config |

### Functions

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `get_capability` | `provider, key, default=None` | `any` | Look up a provider capability |
| `is_paid_provider` | `provider` | `bool` | True if non-zero cost |
| `provider_needs_key` | `provider` | `bool` | True if not ollama/lmstudio |
| `check_hardware` | | `dict` | Detect RAM, GPU, recommend model |
| `list_ollama_models` | | `list[str]` | Installed Ollama models |
| `pull_ollama_model` | `model` | `bool` | Download an Ollama model |
| `classify_error` | `exc` | `(type, message)` | Classify provider exception |
| `chat` | `cfg, messages, stream=False` | `str or Generator` | Send chat completion |
| `simple_complete` | `cfg, prompt` | `str` | One-shot completion |
| `cfg_from_settings` | | `LLMConfig` | Build config from stored settings |
| `chat_with_fallback` | `configs, messages, stream=False` | `(response, config, errors)` | Try configs in order |
| `estimate_tokens` | `text` | `int` | Rough token count |
| `estimate_cost` | `provider, input_text, output_text` | `float` | Estimated USD cost |

---

## media.audio_engine

TTS, binaural beats, ambient pads, and audio processing.

### Constants

| Name | Description |
|------|-------------|
| `SAMPLE_RATE` | 44100 Hz |
| `VOICES` | 13 Edge-TTS voice labels → IDs |
| `BINAURAL_PRESETS` | 5 presets: gamma, beta, alpha, theta, none |
| `SFX_PRESETS` | 8 effects: click, success, unlock, error, xp_gain, level_up, page_turn, collect |

### Functions

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `synth_tts` | `text, out_path, voice_id="en-US-AriaNeural", rate="+0%", pitch="+0Hz"` | `Path` | Synthesize speech (edge-tts + pyttsx3 fallback) |
| `audio_duration` | `path` | `float` | Duration in seconds |
| `generate_binaural` | `duration_s, preset="gamma_40hz", volume=0.18` | `ndarray` | Stereo binaural beat array |
| `generate_ambient` | `duration_s, key_note="A", volume=0.12` | `ndarray` | Stereo ambient pad array |
| `generate_sfx_bytes` | `sfx_name` | `bytes` | WAV bytes for a sound effect |
| `measure_rms_lufs` | `data` | `float` | Estimated loudness in LUFS |
| `normalize_loudness` | `data, target_lufs=-14.0` | `ndarray` | Scale audio to target LUFS |
| `detect_clipping` | `data, threshold=0.99` | `bool` | True if any sample exceeds threshold |
| `auto_gain` | `data, headroom_db=3.0` | `ndarray` | Reduce gain if clipping detected |
| `write_wav_stereo` | `path, data, sample_rate=44100` | `None` | Write stereo WAV file |
| `mix_audio_files` | `tts_path, ambient_path, out_path, tts_vol=1.0, amb_vol=0.3` | `Path` | Mix TTS + ambient to WAV |
| `generate_binaural_wav` | `duration_s, base_freq=200, beat_freq=40, volume=0.25` | `bytes` | Raw WAV bytes for binaural tone |

---

## media.video_engine

Animated lecture video renderer.

### Constants

| Name | Description |
|------|-------------|
| `PALETTE` | 10-colour dungeon-academic palette |

### Functions

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `render_lecture` | `lecture_data, output_dir, chunk_by_scene=False, fps=None, width=None, height=None, suffix="", output_mode="full"` | `list[Path]` | Render lecture to MP4 (full/music_only/narration_only) |
| `batch_render_all` | `output_dir, progress_callback=None` | `dict` | Render all lectures; returns summary |
| `reorder_and_render` | `lecture_data, scene_order, duration_overrides, output_dir` | `Path` | Re-render with custom order/durations |

---

## ui.theme

Dungeon-academic CSS theme and UI widgets.

### Constants

| Name | Description |
|------|-------------|
| `CSS` | Full Streamlit dark theme CSS |
| `DEGREE_SIGILS` | Unicode sigils per degree tier |

### Functions

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `sanitize_llm_output` | `text` | `str` | Strip dangerous HTML/JS from LLM text |
| `inject_theme` | | `None` | Inject CSS into Streamlit page |
| `arcane_header` | `title, subtitle=""` | `None` | ASCII-box header |
| `rune_divider` | `label=""` | `None` | Styled horizontal divider |
| `stat_card` | `label, value, delta="", colour="#00d4ff"` | `None` | Coloured metric card |
| `xp_bar` | `current, maximum, label="XP"` | `None` | ASCII XP progress bar |
| `level_badge` | `level_idx, title` | `None` | Styled level badge |
| `achievement_card` | `title_or_dict, description="", category="", unlocked=False` | `None` | Achievement card |
| `progress_badge` | `status` | `str` | HTML badge for status |
| `deadline_pill` | `seconds_remaining` | `str` | Colour-coded time-remaining pill |
| `render_gpa_display` | `gpa` | `None` | Large GPA with honors label |
| `play_sfx` | `sfx_name` | `None` | Autoplay sound effect |
| `loading_strip` | `text="PROCESSING"` | `None` | Animated loading indicator |
| `completion_burst` | `message="QUEST COMPLETE"` | `None` | Gold celebration banner |
| `degree_display` | `eligible` | `None` | Highest degree with sigil |
| `help_button` | `topic_key, label="[?]"` | `None` | Inline help link |
