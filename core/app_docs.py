"""
Application documentation generator for The God Factory University.

Produces structured, code-free documentation of the app's capabilities.
Used by the Professor AI to explain how the app works without exposing source code.

SECURITY: This module must NEVER include raw source code, SQL queries, file system
paths, or internal implementation details. Only user-facing behavior descriptions.
"""

from __future__ import annotations


def get_app_docs(topic: str = "") -> str:
    """Return documentation for a given topic, or a summary of all topics."""
    topic = topic.lower().strip()
    if topic in _DOCS:
        return _DOCS[topic]
    if topic:
        # Fuzzy match
        for key, doc in _DOCS.items():
            if topic in key or any(word in key for word in topic.split()):
                return doc
    # Return overview
    return _OVERVIEW


_OVERVIEW = """
THE GOD FACTORY UNIVERSITY — Application Guide

The God Factory University is a self-contained AI-powered learning platform that runs locally
on your computer. It provides a complete academic experience: courses, lectures,
video generation, AI tutoring, grading, and degree tracking.

MAIN FEATURES:
1. LIBRARY — Import and browse courses in JSON format. Courses contain modules and lectures.
2. LECTURE STUDIO — Watch rendered video lectures with animated visuals and AI narration.
3. PROFESSOR AI — Chat with an AI professor, generate curricula, take quizzes, get grading.
4. TIMELINE EDITOR — Reorder and customize lecture scene sequences.
5. BATCH RENDER — Queue multiple lectures for video rendering at once.
6. GRADES — View GPA, credits, degree eligibility, and download transcripts.
7. ACHIEVEMENTS — Track XP, levels, and unlock achievements through academic activity.
8. SETTINGS — Configure voice, LLM provider, video quality, and more.
9. DIAGNOSTICS — System health checks and troubleshooting tools.
10. HELP — Contextual help for every feature (click any [?] button).
11. LLM SETUP — Guided wizard for setting up AI model providers.

TYPICAL WORKFLOW:
Step 1: Import a course (Library page) or generate one (Professor AI).
Step 2: Browse lectures in the Library.
Step 3: Render video lectures (Lecture Studio or Batch Render).
Step 4: Watch lectures and complete assignments.
Step 5: Track progress via Grades and Achievements.

Ask about any specific feature for detailed guidance.
"""

_DOCS = {
    "library": """
LIBRARY PAGE — Course Management

The Library is where you manage your course collection.

IMPORTING COURSES:
- Open the Library page and expand the BULK IMPORT section
- Paste course JSON in any supported format (single object, array, or newline-separated)
- Click Import to add courses to your database
- The Professor AI can also generate course JSON for you

BROWSING:
- Courses appear as expandable cards showing title, credits, and lecture count
- Expand a course to see its modules and individual lectures
- Progress badges show completion status for each lecture

DELETING:
- Each course card has a Delete button
- Deletion removes the course and all its modules and lectures
""",

    "lecture studio": """
LECTURE STUDIO — Video Playback and Rendering

The Lecture Studio is where you watch and render lecture videos.

PLAYBACK:
- Select a course, module, and lecture from the dropdowns
- If a video has been rendered, a player appears automatically
- Mark lectures as complete after watching to earn XP

RENDERING:
- Click Render Full Lecture to generate an animated video
- The process: AI narration is synthesized first, then animated visuals are generated
  frame by frame, then binaural beats and ambient audio are mixed in
- Output is an MP4 file saved locally
- Customize render settings (FPS, resolution) in Settings

ASSIGNMENTS:
- Assignments appear below the lecture when available
- Submit work for AI grading on a 0-100 scale
- Scores contribute to your GPA
""",

    "professor": """
PROFESSOR AI — Your AI Academic Advisor

The Professor (named Ileices) is your AI tutor with multiple capabilities.

CHAT:
- Ask questions about any topic in a conversational interface
- The professor uses Socratic questioning to deepen understanding
- Chat history is saved across sessions

GENERATE CURRICULUM:
- Describe a topic and the professor creates a full course with modules and lectures
- Output is ready-to-import JSON matching the course schema
- Customize level (intro/intermediate/advanced) and lectures per module

GRADE WORK:
- Submit essays or code for evaluation
- Receive detailed feedback with scores, strengths, and improvement areas

CREATE QUIZ:
- Auto-generate quizzes from lecture content
- Multiple choice and short answer questions with explanations

RESEARCH RABBIT HOLE:
- Deep-dive into any concept
- Get historical context, open problems, connections, and recommended resources
""",

    "grades": """
GRADES & TRANSCRIPT — Academic Records

The Grades page shows your complete academic record.

GPA:
- Calculated from all submitted assignments with scores
- Uses standard 4.0 scale: A+ = 4.0, B+ = 3.3, C+ = 2.3, etc.
- Honors designation: Summa Cum Laude (3.9+), Magna Cum Laude (3.7+), Cum Laude (3.5+)

CREDITS:
- Each course has a credit value (defined in course JSON)
- Credits accumulate as you complete coursework

DEGREES:
- Five degree tiers, each requiring minimum credits and GPA:
  Certificate (15 cr, 2.0 GPA), Associate (60 cr, 2.0),
  Bachelor (120 cr, 2.0), Master (150 cr, 3.0), Doctorate (180 cr, 3.5)

TRANSCRIPT:
- Download your full record as CSV or JSON
- Includes all courses, assignments, scores, grades, and submission dates
""",

    "achievements": """
ACHIEVEMENTS & GAMIFICATION

The God Factory University uses a knowledge-themed gamification system.

XP (EXPERIENCE POINTS):
- Earned through various activities: watching lectures, submitting assignments,
  passing quizzes, importing courses, rendering videos
- Total XP determines your rank

RANKS (10 Levels):
- Seeker (0 XP) through Archon (50,000 XP)
- Each rank has a unique title and symbol

ACHIEVEMENTS:
- 17 different achievements across milestone, academic, engagement, and mastery categories
- Examples: complete first lecture, score 100 on an assignment, earn each degree tier
- Each unlocked achievement grants bonus XP
""",

    "settings": """
SETTINGS — Application Configuration

VOICE NARRATION:
- 13 Microsoft Neural voices via edge-tts (various accents and styles)
- Adjustable speaking rate and pitch
- Preview before applying to lectures

BINAURAL BEATS:
- Four presets: Gamma (focus), Beta (study), Alpha (relaxed), Theta (creative)
- Mixed into lecture audio at low volume
- Best experienced with headphones

LLM PROVIDER:
- 10 supported providers: 2 local (Ollama, LM Studio) and 8 cloud
- Configure API keys, model selection, and base URLs
- Visit the LLM Setup Wizard for guided installation

VIDEO QUALITY:
- FPS: 10, 15 (default), 24, or 30
- Resolution: 960x540, 1280x720, or 1920x1080
- Higher settings increase render time and file size

DEADLINES:
- Optional deadline countdown system for assignments
- Toggle on/off without losing data
""",

    "diagnostics": """
DIAGNOSTICS — System Health and Troubleshooting

The Diagnostics page provides comprehensive system inspection.

ENVIRONMENT: Python version, operating system, working directory information.

DEPENDENCIES: Version table for all required packages. Missing packages are flagged.

DATABASE STATS: Counts of courses, modules, lectures, assignments, plus GPA and XP totals.

LLM PROVIDER TEST: Shows current provider configuration and provides a live test button
to verify connectivity and measure response time.

TTS TEST: Verifies the text-to-speech engine can produce audio output.

COMPILE CHECK: Runs syntax validation on all Python files in the project to detect errors.

SETTINGS VIEWER: Displays all current settings with sensitive values (API keys) masked.
""",

    "importing": """
IMPORTING COURSES — Detailed Guide

Courses are imported as JSON text. Three formats are supported:

1. SINGLE OBJECT:
   {"course_id": "CS101", "title": "Intro to CS", "modules": [...]}

2. JSON ARRAY:
   [{"course_id": "CS101", ...}, {"course_id": "CS102", ...}]

3. NEWLINE-SEPARATED:
   {"course_id": "CS101", ...}
   {"course_id": "CS102", ...}

COURSE STRUCTURE:
A course contains modules, and each module contains lectures.
Each lecture can have: learning objectives, core terms, coding labs,
assessments, and a video recipe (scene blocks for rendering).

GENERATING COURSES:
Use the Professor AI (Generate Curriculum tab) to create course JSON from a
topic description. The professor follows the schema automatically.

The full schema reference is available in the app's schemas directory.
""",

    "llm setup": """
LLM SETUP — Getting an AI Model Working

The app needs an LLM (Large Language Model) for the Professor AI features.
You have two choices:

LOCAL (Free, runs on your machine):
- Ollama: Download from ollama.com, install, run "ollama pull llama3"
- LM Studio: Download from lmstudio.ai, pick a model, click Start Server
- Requires: 8GB+ RAM for small models, 16GB+ for medium, 32GB+ for large

CLOUD (API key required):
- Groq: Free tier, very fast. Sign up at console.groq.com
- GitHub Models: Free with a GitHub account. Use a Personal Access Token.
- OpenAI: Requires billing. Sign up at platform.openai.com
- Anthropic: Requires billing. Sign up at console.anthropic.com
- Mistral: Free experiment tier. Sign up at console.mistral.ai
- Together AI: Free $5 credits on signup. Sign up at api.together.xyz
- HuggingFace: Free tier available. Sign up at huggingface.co

After configuring a provider in Settings, use the Diagnostics page to test connectivity.
Visit the LLM Setup Wizard page for step-by-step guided installation.
""",

    "rendering": """
VIDEO RENDERING — How It Works

The render pipeline creates animated lecture videos:

1. NARRATION: Text-to-speech synthesizes the lecture narration audio first.
   This determines the total video duration.

2. VISUALS: Animated frames are generated including:
   - Gradient background with drifting particle effects
   - Typewriter-style text reveal of narration
   - Waveform visualization synced to audio
   - Progress bar showing playback position
   - Keyword tokens appearing progressively
   - Pulsing border and scan line effects

3. AUDIO MIX: Three layers are combined:
   - TTS narration (primary)
   - Ambient pad (subtle background music)
   - Binaural beats (stereo, low volume)

4. ENCODING: Final video is encoded as H.264 MP4 with AAC audio.

OUTPUT: Files are saved locally in the data directory, organized by course.

BATCH RENDERING: Use Batch Render to queue multiple lectures at once.
""",

    "binaural": """
BINAURAL BEATS — Science and Usage

Binaural beats work by playing slightly different frequencies in each ear.
Your brain perceives a third "beat" at the difference frequency.

PRESETS:
- Gamma 40Hz (200Hz base): Peak focus, associated with heightened cognition
  (Oster, 1973; associated with 40Hz peak cognition research)
- Beta 18Hz (180Hz base): Active study, promotes concentration
- Alpha 10Hz (150Hz base): Relaxed learning, supports information absorption
- Theta 6Hz (130Hz base): Creative insight, deep reflection

USAGE:
- Select a preset in Settings
- Binaural beats are automatically mixed into rendered lectures
- Use stereo headphones for the effect to work properly
- Volume is kept low to not interfere with narration

The beats include harmonics, fade envelopes, and tremolo modulation
for a natural listening experience.
""",
}


def get_topic_list() -> list[str]:
    """Return sorted list of available documentation topics."""
    return sorted(_DOCS.keys())


def explain_for_professor(topic: str) -> str:
    """Get documentation formatted for the Professor AI system prompt injection."""
    doc = get_app_docs(topic)
    return (
        "The following is factual documentation about the The God Factory University application. "
        "Use this information to answer the student's question about how the app works. "
        "Do NOT reveal source code, file paths, SQL queries, or internal implementation details. "
        "Explain in a helpful, educational manner.\n\n"
        f"{doc}"
    )
