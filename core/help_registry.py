"""
Central help registry for The God Factory University.

Maps (page_key, topic_key) -> help entry with title, text, and anchor.
Used by the help_button() utility and pages/10_Help.py.
"""

from __future__ import annotations

# ─── Help entry structure ─────────────────────────────────────────────────────
# Each entry: {"title": str, "anchor": str, "text": str}
# anchor is used for URL fragment navigation: 10_Help.py?topic=<anchor>

HELP_ENTRIES: dict[str, dict] = {}


def _reg(anchor: str, title: str, text: str) -> None:
    HELP_ENTRIES[anchor] = {"title": title, "anchor": anchor, "text": text}


# ─── Dashboard ────────────────────────────────────────────────────────────────
_reg("dashboard-overview", "Dashboard Overview",
     "The Dashboard is the home screen of The God Factory University. It shows your current "
     "status at a glance: total courses, lectures completed, total XP earned, and "
     "your current rank in the progression hierarchy.\n\n"
     "Below the stats you will find a Quick Start guide walking you through the "
     "recommended workflow: import a course, review lectures, render videos, "
     "watch them, submit assignments, earn XP, and unlock achievements.")

_reg("system-health", "System Health Panel",
     "The System Health section on the Dashboard runs 6 automatic checks:\n\n"
     "- **Database**: Verifies the SQLite database file exists and is accessible.\n"
     "- **FFmpeg**: Checks that the bundled FFmpeg binary is found (used for video encoding).\n"
     "- **TTS Engine**: Tests that edge-tts or pyttsx3 can synthesize speech.\n"
     "- **LLM Config**: Checks whether an LLM provider is configured in Settings.\n"
     "- **Video Engine**: Verifies the video rendering module loads without errors.\n"
     "- **Audio Engine**: Verifies the audio engine module loads without errors.\n\n"
     "Green = working. Red = needs attention. Expand the panel for details.")

_reg("xp-and-levels", "XP and Levels",
     "XP (Experience Points) are earned through activities:\n\n"
     "- Watching lectures (+10 XP)\n"
     "- Submitting assignments (+25 XP)\n"
     "- Passing quizzes (+15 XP)\n"
     "- Importing courses (+10 XP per course)\n"
     "- Rendering videos (+5 XP)\n\n"
     "10 Ranks:\n"
     "Seeker (0) -> Initiate (100) -> Scholar (300) -> Adept (700) -> "
     "Expert (1500) -> Sage (3000) -> Transcendent (6000) -> Grandmaster (10000) -> "
     "Luminary (20000) -> Archon (50000)")

# ─── Library ──────────────────────────────────────────────────────────────────
_reg("importing-courses", "Importing Courses",
     "Open the Library page and expand the BULK IMPORT section. Paste JSON in any of "
     "these formats:\n\n"
     "1. **Single course object**: `{\"course_id\": \"CS101\", \"title\": \"...\", \"modules\": [...]}`\n"
     "2. **JSON array**: `[{...}, {...}]`\n"
     "3. **Newline-separated objects**: one JSON object per line\n\n"
     "The template is in `schemas/course_schema.json` and validation uses "
     "`schemas/course_validation_schema.json`. You can also have "
     "Professor AI generate a course for you on the Professor AI page.\n\n"
     "Assignment batches (using `schemas/assignment_schema.json`) are also "
     "detected and imported automatically.")

_reg("course-json-schema", "Course JSON Schema",
     "Every course has this structure:\n\n"
     "- **course_id**: Unique identifier (e.g. \"CS101\")\n"
     "- **title**: Course name\n"
     "- **description**: Brief description\n"
     "- **credits**: Integer (used for degree progress)\n"
     "- **modules**: Array of modules, each containing:\n"
     "  - **module_id**, **title**\n"
     "  - **lectures**: Array of lectures with:\n"
     "    - lecture_id, title, duration_min, prerequisites, learning_objectives,\n"
     "      core_terms, coding_lab, assessment, video_recipe (scene_blocks)\n\n"
     "See `schemas/SCHEMA_GUIDE.md` for the full prompt to give an LLM to generate "
     "valid course JSON.")

_reg("browsing-courses", "Browsing Courses",
     "The Library page lists all imported courses as expandable cards. Each card shows:\n\n"
     "- Course ID and title\n"
     "- Number of lectures and credit value\n"
     "- Source (how it was imported)\n"
     "- Modules and lectures nested inside, with progress badges showing completion status")

_reg("deleting-courses", "Deleting Courses",
     "Each course card in the Library has a Delete button. Deleting a course removes "
     "the course record and all associated modules and lectures from the database. "
     "This action cannot be undone. Progress and assignment records may become orphaned.")

# ─── Lecture Studio ───────────────────────────────────────────────────────────
_reg("playing-lectures", "Playing Lectures",
     "In Lecture Studio, select a course, module, and lecture. If the lecture has been "
     "rendered, a video player appears. Clicking Play streams the MP4 file directly. "
     "When you finish watching, mark the lecture as complete to earn XP and update "
     "your progress tracker.")

_reg("rendering-lecture", "Rendering a Lecture",
     "Click 'Render Full Lecture' to generate an animated video:\n\n"
     "1. TTS narration is synthesized first (determines video length)\n"
     "2. Animated frames are generated: particles, typewriter text, waveform, progress bar\n"
     "3. Binaural beats and ambient pad are mixed with narration\n"
     "4. Final MP4 is encoded with H.264 video + AAC audio\n\n"
     "Output goes to `data/<course_id>/` by default. Render settings (FPS, resolution) "
     "can be changed in Settings.")

_reg("scene-chunks", "Scene Chunks",
     "Scene chunk mode exports each scene block as a separate video file. This is "
     "useful for editing individual sections or importing into external video editors.")

_reg("assignment-submission", "Assignment Submission",
     "Assignments appear below the lecture player. Submit your work (text or code), "
     "and it will be scored on a 0-100 scale. Scores map to letter grades:\n\n"
     "A+ (97+) = 4.0 ... F (below 60) = 0.0\n\n"
     "Graded assignments contribute to your GPA and credit accumulation.")

# ─── Professor AI ─────────────────────────────────────────────────────────────
_reg("professor-chat", "Chat with Professor",
     "The Chat tab gives you a two-way conversation with Ileices, your AI professor. "
     "Ask any question about course material. The professor uses Socratic questioning "
     "to guide understanding. Chat history is saved per session.\n\n"
     "Requires a working LLM provider configured in Settings or the LLM Setup Wizard.")

_reg("generate-curriculum", "Generate Curriculum",
     "The Generate Curriculum tab lets the AI create a complete course JSON from a "
     "topic description. Provide:\n\n"
     "- Topic (e.g. \"Introduction to Machine Learning\")\n"
     "- Level (introductory, intermediate, advanced)\n"
     "- Lectures per module (default: 3)\n\n"
     "The professor generates JSON matching the course schema. Review it, edit if "
     "needed, then import directly into the Library.")

_reg("grade-work", "Grade Work",
     "Submit essays or code for AI grading. The professor evaluates against a rubric "
     "and returns:\n\n"
     "- Score (0-100)\n"
     "- Strengths identified\n"
     "- Areas for improvement\n"
     "- Detailed feedback\n\n"
     "Essay grading evaluates clarity, argument strength, evidence, and writing quality. "
     "Code grading evaluates correctness, style, efficiency, and documentation.")

_reg("create-quiz", "Create Quiz",
     "Auto-generate quizzes from any lecture. The AI creates multiple-choice and "
     "short-answer questions with explanations for each answer. Configure the number "
     "of questions. Quizzes can be taken immediately for self-assessment.")

_reg("research-rabbit-hole", "Research Rabbit Hole",
     "Enter any keyword or concept to get a deep exploration:\n\n"
     "- Historical context and origins\n"
     "- Open problems and current research\n"
     "- Connections to other fields\n"
     "- Recommended papers and resources\n\n"
     "Great for going deeper on topics that interest you.")

# ─── Timeline Editor ──────────────────────────────────────────────────────────
_reg("reordering-scenes", "Reordering Scenes",
     "The Timeline Editor shows all scene blocks for a lecture. Use the up/down "
     "buttons to reorder scenes. You can also override the duration of individual "
     "scenes. Click 'Render with Edits' to create a new video with your custom order.")

_reg("exporting-timeline", "Exporting Timeline",
     "Export the modified scene order as JSON for backup or transfer to another instance.")

# ─── Batch Render ─────────────────────────────────────────────────────────────
_reg("batch-render", "Batch Render",
     "Queue multiple lectures for rendering at once. Select lectures from any course, "
     "choose FPS and resolution, then start the batch. Progress is shown as a bar. "
     "Rendered files are saved to the data directory.\n\n"
     "Prompt Pack Export: Generate external tool prompts in Runway, Pika, or ComfyUI "
     "formats for importing visual descriptions into AI video generators.")

# ─── Grades ───────────────────────────────────────────────────────────────────
_reg("gpa-calculation", "GPA Calculation",
     "GPA is calculated from all submitted assignments with max_score > 0:\n\n"
     "Each assignment's percentage score maps to a GPA point value:\n"
     "A+ (97+) = 4.0, A (93-96) = 4.0, A- (90-92) = 3.7\n"
     "B+ (87-89) = 3.3, B (83-86) = 3.0, B- (80-82) = 2.7\n"
     "C+ (77-79) = 2.3, C (73-76) = 2.0, C- (70-72) = 1.7\n"
     "D+ (67-69) = 1.3, D (60-66) = 1.0, F (<60) = 0.0\n\n"
     "Cumulative GPA = average of all assignment GPA points.\n\n"
     "Honors: Summa Cum Laude (3.9+), Magna Cum Laude (3.7+), Cum Laude (3.5+)")

_reg("degree-eligibility", "Degree Eligibility",
     "Degrees require minimum credits AND minimum GPA:\n\n"
     "- Certificate: 15 credits, 2.0 GPA\n"
     "- Associate: 60 credits, 2.0 GPA\n"
     "- Bachelor: 120 credits, 2.0 GPA\n"
     "- Master: 150 credits, 3.0 GPA\n"
     "- Doctorate: 180 credits, 3.5 GPA\n\n"
     "Credits are earned per course (defined in course JSON). Completing assignments "
     "within a course contributes to its credit value.")

_reg("transcript-download", "Transcript Download",
     "Download your academic record as CSV or JSON. The transcript includes:\n\n"
     "- Course name and ID\n"
     "- Assignment title, type, and score\n"
     "- Letter grade and GPA points\n"
     "- Submission date\n"
     "- Cumulative GPA and total credits")

# ─── Achievements ─────────────────────────────────────────────────────────────
_reg("achievement-system", "Achievement System",
     "17 achievements across categories (milestone, academic, engagement, mastery). "
     "Each has an XP reward. Achievements unlock automatically when conditions are met:\n\n"
     "- first_lecture: Complete your first lecture\n"
     "- ten_lectures: Complete 10 lectures\n"
     "- perfect_score: Score 100 on any assignment\n"
     "- degree_cert through degree_doctor: Earn each degree tier\n"
     "- xp_1000, xp_5000: Accumulate XP milestones\n"
     "- And more...")

_reg("level-system", "Level System",
     "10 progression ranks based on total XP:\n\n"
     "| Level | Title | XP Required |\n"
     "|-------|-------|-------------|\n"
     "| 1 | Seeker | 0 |\n"
     "| 2 | Initiate | 100 |\n"
     "| 3 | Scholar | 300 |\n"
     "| 4 | Adept | 700 |\n"
     "| 5 | Expert | 1,500 |\n"
     "| 6 | Sage | 3,000 |\n"
     "| 7 | Transcendent | 6,000 |\n"
     "| 8 | Grandmaster | 10,000 |\n"
     "| 9 | Luminary | 20,000 |\n"
     "| 10 | Archon | 50,000 |")

# ─── Settings ─────────────────────────────────────────────────────────────────
_reg("voice-settings", "Voice Settings",
     "Configure the TTS (Text-to-Speech) engine used for lecture narration:\n\n"
     "- **Voice**: 13 Microsoft Neural voices via edge-tts (male and female, US/UK/AU/CA accents)\n"
     "- **Rate**: Speed adjustment (-50 to +50). Positive = faster.\n"
     "- **Pitch**: Pitch adjustment (-50 to +50). Positive = higher.\n\n"
     "Use the Preview button to hear a sample before rendering lectures. "
     "Falls back to pyttsx3 offline engine if edge-tts is unavailable.")

_reg("binaural-beats", "Binaural Beats",
     "Binaural beats are an auditory technique where slightly different frequencies "
     "are played in each ear, creating a perceived beat at the difference frequency.\n\n"
     "Presets:\n"
     "- **Gamma 40Hz**: Peak focus and cognition (Oster 1973)\n"
     "- **Beta 18Hz**: Active study and concentration\n"
     "- **Alpha 10Hz**: Relaxed learning and absorption\n"
     "- **Theta 6Hz**: Creative insight and deep reflection\n\n"
     "Binaural beats are mixed into lecture videos at low volume. "
     "Use headphones for the full stereo effect.")

_reg("llm-provider-settings", "LLM Provider Settings",
     "Configure which AI model powers the Professor and curriculum generation:\n\n"
     "**Local (Free, runs on your machine)**:\n"
     "- Ollama: Install from ollama.com, pull models with `ollama pull <model>`\n"
     "- LM Studio: Download from lmstudio.ai, load a model, start server\n\n"
     "**Cloud (API key required)**:\n"
     "- OpenAI (gpt-4o, gpt-4o-mini) — platform.openai.com\n"
     "- Anthropic Claude (claude-3.5-sonnet) — console.anthropic.com\n"
     "- Groq (free tier, very fast) — console.groq.com\n"
     "- GitHub Models (free with PAT) — github.com/settings/tokens\n"
     "- Mistral AI — console.mistral.ai\n"
     "- Together AI (free $5 credit) — api.together.xyz\n"
     "- HuggingFace — huggingface.co/settings/tokens\n\n"
     "For detailed setup instructions, visit the LLM Setup Wizard page.")

_reg("video-settings", "Video Settings",
     "Control video render quality:\n\n"
     "- **FPS**: 10 (fast draft), 15 (default balanced), 24 (smooth), 30 (cinematic)\n"
     "- **Resolution**: 960x540 (default), 1280x720, 1920x1080\n"
     "- **Render Backend**: local (built-in engine), or external prompts (Runway/Pika/ComfyUI)\n\n"
     "Higher FPS and resolution increase render time and file size significantly.")

_reg("deadline-system", "Deadline System",
     "When deadlines are enabled in Settings, assignments show due dates with "
     "countdown timers. Overdue assignments are flagged. Late submissions may affect "
     "grading (late policy is configurable).\n\n"
     "Toggle deadlines on/off in Settings without losing existing deadline data.")

# ─── Diagnostics ──────────────────────────────────────────────────────────────
_reg("diagnostics-page", "Diagnostics Page",
     "The Diagnostics page provides a comprehensive system health overview:\n\n"
     "- **Environment**: Python version, platform, working directory\n"
     "- **Dependencies**: Version table for all 14 required packages\n"
     "- **Database Stats**: Course/module/lecture counts, GPA, credits, XP\n"
     "- **LLM Provider**: Current configuration with live connectivity test\n"
     "- **Audio Engine**: Voice and binaural beat configuration\n"
     "- **Video Settings**: FPS, resolution, render backend\n"
     "- **Compile Check**: Validates all 17 Python files for syntax errors\n"
     "- **Settings Dump**: All settings with API keys masked")

_reg("compile-check", "Compile Check",
     "The compile check runs `py_compile` on every Python file in the project. "
     "This catches syntax errors and basic import issues. A green checkmark means "
     "the file compiles cleanly. A red X means there is a syntax error that needs fixing.")

_reg("llm-test", "LLM Connectivity Test",
     "The LLM test button sends a simple prompt to the configured provider and "
     "measures response time. It verifies:\n\n"
     "- API key is valid (for cloud providers)\n"
     "- Provider endpoint is reachable\n"
     "- Model exists and can generate responses\n"
     "- Approximate response latency\n\n"
     "If the test fails, check your provider settings or visit the LLM Setup Wizard.")

# ─── Additional topics ────────────────────────────────────────────────────────
_reg("first-launch", "First Launch",
     "On your very first launch, The God Factory University:\n\n"
     "1. Creates the SQLite database and seeds default settings\n"
     "2. Seeds 17 achievement definitions and weekly quests\n"
     "3. Auto-imports the bundled demo course from `notes.txt` (if present)\n"
     "4. Opens the Dashboard at http://localhost:8501\n\n"
     "You can re-run setup.bat safely — it is fully idempotent and will not "
     "duplicate data or overwrite your progress.")

_reg("render-settings", "Render Settings",
     "Control the quality and format of rendered lecture videos:\n\n"
     "- **FPS**: 10 (fast draft) · 15 (default) · 24 (smooth) · 30 (cinematic)\n"
     "- **Resolution**: 960×540 (default) · 1280×720 · 1920×1080\n"
     "- **Output mode**: full (narration + music) · music_only · narration_only\n"
     "- **Render backend**: local engine · Runway / Pika / ComfyUI prompts\n\n"
     "Higher quality settings increase render time and file size. Use 'fast draft' "
     "(10 fps, 960×540) for previews, then render final at higher quality.")

_reg("prompt-pack-export", "Prompt Pack Export",
     "The batch pipeline can generate prompt packs for external video tools:\n\n"
     "- **Runway ML**: Cinematic scene prompts optimised for Gen-2/Gen-3\n"
     "- **Pika Labs**: Animation-style prompts with motion directives\n"
     "- **ComfyUI**: Structured prompt/negative-prompt pairs with metadata\n\n"
     "Prompt packs are saved as JSONL in the `data/` directory. Import the JSON "
     "into your preferred external tool to generate higher-fidelity video clips.")

_reg("assignment-records", "Assignment Records",
     "Each assignment tracks:\n\n"
     "- **Score** (0–100) and derived letter grade (A+ through F)\n"
     "- **Feedback** from the Professor AI or manual entry\n"
     "- **Deadline status**: on-time, late (with penalty), or no deadline\n"
     "- **Weight** for GPA calculation (default 1.0)\n"
     "- **Term** grouping for transcript organisation\n\n"
     "View all assignment records on the Grades page, grouped by term.")

_reg("xp-events", "XP Events",
     "Actions that earn XP:\n\n"
     "| Action | XP |\n"
     "|--------|----|\n"
     "| Complete a lecture | +10 |\n"
     "| Submit assignment | +25 |\n"
     "| Import a course (bulk) | +25 per object |\n"
     "| Generate curriculum | +100 |\n"
     "| Consult Professor | +5 |\n"
     "| Unlock achievement | varies (25–200) |\n"
     "| Complete weekly quest | varies (50–100) |\n\n"
     "**Streak bonus**: +5% per consecutive day (max +50% at 10-day streak).\n"
     "View your complete XP history on the Achievements page.")

# ─── LLM Setup Wizard ─────────────────────────────────────────────────────────
_reg("llm-setup-wizard", "LLM Setup Wizard",
     "A guided walkthrough for configuring your AI model provider.\n\n"
     "**Step 1 — Choose Your Path:**\n"
     "- **Local**: Free models running on your machine (Ollama or LM Studio).\n"
     "  Requires 8GB+ RAM. Works offline, fully private.\n"
     "- **Cloud**: Remote API services (OpenAI, Anthropic, Groq, GitHub, Mistral, "
     "Together, HuggingFace). Some offer free tiers.\n\n"
     "**Step 2 — Hardware Profile:**\n"
     "The wizard detects your RAM, GPU, and disk space, then recommends an "
     "appropriate model size.\n\n"
     "**Step 3 — Provider Setup:**\n"
     "Step-by-step instructions for your chosen provider: account creation, "
     "API key generation, model selection, and one-click connection testing.\n\n"
     "**Ollama Model Catalog:**\n"
     "50+ models organized by size (Tiny/Small/Medium/Large/XL). Pull models "
     "directly from the UI or copy the terminal command.\n\n"
     "**Troubleshooting:**\n"
     "Each provider includes a troubleshooting guide for common connection issues.")

_reg("llm-local-setup", "Local LLM Setup (Ollama / LM Studio)",
     "**Ollama** — Lightweight CLI tool for running LLMs locally:\n"
     "1. Install from ollama.com\n"
     "2. Pull a model: `ollama pull llama3.2`\n"
     "3. Service auto-starts on port 11434\n"
     "4. The wizard auto-detects running Ollama and lists installed models\n\n"
     "**LM Studio** — Desktop app with visual model management:\n"
     "1. Install from lmstudio.ai\n"
     "2. Download a model via the Discover tab\n"
     "3. Start the server on the Local Server tab (port 1234)\n"
     "4. The wizard auto-detects the running server\n\n"
     "**Model Size Guide:**\n"
     "| Size | VRAM | RAM (CPU) | Examples |\n"
     "|------|------|-----------|----------|\n"
     "| 1-3B | 2 GB | 4 GB | phi3:mini, tinyllama |\n"
     "| 7-8B | 5 GB | 8 GB | llama3.1:8b, mistral:7b |\n"
     "| 13B | 9 GB | 16 GB | codellama:13b |\n"
     "| 30B+ | 20 GB | 32 GB | codellama:34b |\n"
     "| 70B | 40 GB | 64 GB | llama3.1:70b |")

_reg("llm-cloud-setup", "Cloud LLM Setup",
     "Cloud providers ranked by ease of getting started:\n\n"
     "1. **Groq** — FREE tier, no payment needed, extremely fast (~500 tok/s)\n"
     "2. **GitHub Models** — FREE with any GitHub account (Personal Access Token)\n"
     "3. **Together AI** — FREE $5 credit on signup\n"
     "4. **HuggingFace** — FREE tier (rate-limited, cold-start delays)\n"
     "5. **Mistral AI** — FREE experiment tier\n"
     "6. **OpenAI** — PAID, best quality (gpt-4o-mini is affordable)\n"
     "7. **Anthropic** — PAID, 200K context window (great for long docs)\n\n"
     "Each provider page includes: signup link, step-by-step key generation, "
     "model selection, one-click Save & Test, and troubleshooting tips.")

# ─── Agent Dashboard ──────────────────────────────────────────────────────────
_reg("agent-dashboard", "Agent Dashboard",
     "The Agent is an autonomous task execution engine powered by Professor Ileices.\n\n"
     "**How it works:**\n"
     "1. Describe a task (e.g. 'Create a full course on Quantum Computing')\n"
     "2. Configure execution mode, step limits, and tool categories\n"
     "3. Launch the agent — it thinks, calls tools, and iterates until done\n\n"
     "**Execution Modes:**\n"
     "- **Bounded**: Stops after N steps (configurable, default 20)\n"
     "- **Unlimited**: Runs until the task is complete or blocked\n\n"
     "**Review Modes:**\n"
     "- **Auto**: Tools execute immediately\n"
     "- **Review**: Drafts are queued for your approval before executing\n\n"
     "**Rate Limit**: Adds a delay between steps (0-10s) to avoid API throttling.\n\n"
     "The agent has access to 17 tools across categories: course management, "
     "video production, validation, and search. You can enable/disable tool "
     "categories in the sidebar.")

_reg("agent-tools", "Agent Tools Reference",
     "17 tools available to the agent:\n\n"
     "**Course Management:**\n"
     "- create_course_outline, add_module, add_lecture, add_assignment\n"
     "- get_course_manifest, get_all_courses_summary, search_courses\n\n"
     "**Import & Validation:**\n"
     "- validate_and_import (validates JSON against schema and imports)\n\n"
     "**Video & Media:**\n"
     "- list_scenes, render_lecture, batch_render_lectures\n\n"
     "**Search & Analysis:**\n"
     "- search_courses (find existing courses by keyword)\n\n"
     "Tools marked [LOCKED] require review mode approval before execution.")

_reg("agent-job-history", "Agent Job History",
     "All agent jobs are persisted and visible in the Job History section:\n\n"
     "- **[OK]** Completed successfully\n"
     "- **[..]** Currently running\n"
     "- **[||]** Paused (can be resumed)\n"
     "- **[!!]** Failed (can be resumed or deleted)\n"
     "- **[~~]** Pending\n\n"
     "Click [?] on any job to view its full step log. You can resume paused/failed "
     "jobs or delete completed ones.")

# ─── Qualifications ───────────────────────────────────────────────────────────
_reg("qualifications-dashboard", "Qualifications Dashboard",
     "Track your progress toward real-world academic benchmark equivalencies.\n\n"
     "**What are qualifications?**\n"
     "Qualifications map your coursework against real university program requirements. "
     "As you complete courses and assignments, the system evaluates how your work "
     "compares to benchmarks from accredited institutions.\n\n"
     "**Benchmark Comparison:**\n"
     "- Topic Coverage: percentage of benchmark topics covered by your courses\n"
     "- Hours Progress: study hours logged vs. required\n"
     "- Rigor Rating: quality assessment of your coursework depth\n\n"
     "**Gap Analysis:**\n"
     "Shows remaining topics needed to match each benchmark, with a roadmap of "
     "completed and remaining courses.\n\n"
     "**Status Indicators:**\n"
     "- [OK] Earned — qualification fully met\n"
     "- [..] In Progress — partially completed\n"
     "- [--] Locked — not yet started")

# ─── Placement Testing ────────────────────────────────────────────────────────
_reg("placement-testing", "Placement Testing",
     "Take an adaptive placement exam to discover your starting level in any subject.\n\n"
     "1. Select a domain and optional sub-field\n"
     "2. Answer 10 questions of increasing difficulty\n"
     "3. Difficulty adapts based on your correctness streak\n"
     "4. Receive a recommended starting level (beginner / intermediate / advanced)\n\n"
     "Results are saved and can be reviewed in your test history.")

# ─── Test Prep ────────────────────────────────────────────────────────────────
_reg("test-prep", "Standardized Test Prep",
     "Practice for standardized tests with timed sessions and score reports:\n\n"
     "- **GED** : Reasoning Through Language Arts, Mathematical Reasoning, Science, Social Studies\n"
     "- **SAT**: Reading, Writing & Language, Math (No Calc), Math (Calculator)\n"
     "- **ACT**: English, Math, Reading, Science\n"
     "- **GRE**: Verbal Reasoning, Quantitative Reasoning, Analytical Writing\n\n"
     "Each practice session has 10 questions with a 10-minute timer.\n"
     "Score reports include approximate percentile estimates.")

# ─── Programs & Curriculum ────────────────────────────────────────────────────
_reg("programs-overview", "Programs & Curriculum",
     "Browse and enroll in degree programs:\n\n"
     "- **Certificate**: 15 credits minimum\n"
     "- **Associate**: 60 credits\n"
     "- **Bachelor**: 120 credits\n"
     "- **Master**: 150 credits\n"
     "- **Doctorate**: 180 credits\n\n"
     "Track progress toward each program with credit completion bars.\n"
     "Programs are pre-seeded from multiple schools and disciplines.")

# ─── Student Profile ──────────────────────────────────────────────────────────
_reg("student-profile", "Student Profile",
     "Manage your academic identity and preferences:\n\n"
     "- **Display Name**: Your name shown throughout the app\n"
     "- **Grade Level**: K through Postdoctoral (affects course recommendations)\n"
     "- **Learning Style**: Visual, Auditory, Reading/Writing, or Kinesthetic\n"
     "- **Study Pace**: Relaxed, Moderate, or Intensive\n\n"
     "Also shows your academic summary: rank, XP, GPA, credits, and study streak.")

# ─── Statistics Dashboard ─────────────────────────────────────────────────────
_reg("statistics-dashboard", "Statistics Dashboard",
     "Your analytics dashboard with key academic metrics:\n\n"
     "- **Overview cards**: Study hours, lectures completed, assignments, GPA, credits, XP\n"
     "- **Daily Activity**: Bar chart of actions per day (last 30 days)\n"
     "- **Activity Breakdown**: Event types ranked by frequency\n"
     "- **Grade Distribution**: How your scores spread across A/B/C/D/F ranges\n\n"
     "Activity is automatically logged as you use the app.")


def get_help(anchor: str) -> dict | None:
    """Return a help entry by anchor key, or None if not found."""
    return HELP_ENTRIES.get(anchor)


def get_all_help() -> dict[str, dict]:
    """Return all help entries."""
    return HELP_ENTRIES
