# The God Factory University

An AI-powered university built with Python and Streamlit. Generates animated lecture videos with neural narration, binaural beats, and a dungeon-academic theme. Features a Professor AI advisor, grading system with GPA/degrees, achievements, and support for 10 LLM providers (local and cloud).

---

## Quick Start

### Windows (Easiest)

1. Install [Python 3.9+](https://www.python.org/downloads/) -- check **"Add Python to PATH"** during install
2. Double-click **`DOUBLE_CLICK_SETUP_AND_START.bat`**
3. Wait for first-time setup to finish (installs dependencies, creates database)
4. Browser opens automatically at `http://localhost:8501`

Or from a terminal:
```powershell
.\setup.bat
.\start.bat
```

### macOS

```bash
# Install Python if needed
brew install python@3.11

# Clone and run
git clone https://github.com/Ileices/The_God_Factory_University.git
cd The_God_Factory_University
chmod +x setup.sh start.sh
./setup.sh
./start.sh
```

### Linux (Ubuntu/Debian)

```bash
# Install Python and venv
sudo apt update
sudo apt install python3 python3-venv python3-pip

# Clone and run
git clone https://github.com/Ileices/The_God_Factory_University.git
cd The_God_Factory_University
chmod +x setup.sh start.sh
./setup.sh
./start.sh
```

### Linux (Fedora/RHEL)

```bash
sudo dnf install python3 python3-pip
git clone https://github.com/Ileices/The_God_Factory_University.git
cd The_God_Factory_University
chmod +x setup.sh start.sh
./setup.sh
./start.sh
```

---

## What It Does

- **Library** -- Browse and import courses (paste JSON from any LLM)
- **Lecture Studio** -- Watch animated lectures with neural TTS narration and binaural beats
- **Professor AI** -- Chat, generate curricula, grade work, create quizzes, deep research
- **Timeline Editor** -- Reorder scenes, adjust durations, re-render
- **Batch Render** -- Queue lectures for overnight rendering
- **Grades & Transcript** -- GPA calculation, degree progress (Certificate through Doctorate), transcript export
- **Achievements** -- XP system, 10 dungeon ranks (Seeker to Archon), milestone badges
- **Settings** -- Voice selection, binaural presets, LLM provider config, video quality profiles
- **Diagnostics** -- System health, dependency checks, provider connectivity tests
- **Help System** -- Contextual [?] buttons on every page, comprehensive help page
- **LLM Setup Wizard** -- Step-by-step setup for all 10 providers with auto-detection

## LLM Provider Support

| Provider | Type | Cost | Setup |
|----------|------|------|-------|
| Ollama | Local | Free | Install from ollama.com |
| LM Studio | Local | Free | Install from lmstudio.ai |
| Groq | Cloud | Free tier | console.groq.com |
| GitHub Models | Cloud | Free | GitHub PAT |
| OpenAI | Cloud | Paid | platform.openai.com |
| Anthropic | Cloud | Paid | console.anthropic.com |
| Mistral | Cloud | Free tier | console.mistral.ai |
| Together AI | Cloud | Free $5 | api.together.xyz |
| HuggingFace | Cloud | Free tier | huggingface.co |
| Cohere | Cloud | Free trial | dashboard.cohere.com |

Use the in-app **LLM Setup Wizard** (page 11) for guided configuration of any provider.

## Project Structure

```
app.py                  Main dashboard / entry point
core/
  database.py           SQLite persistence (courses, grades, XP, settings)
  help_registry.py      32 contextual help entries
  app_docs.py           Professor-readable app documentation (11 topics)
llm/
  providers.py          Universal LLM client (10 providers)
  professor.py          Professor AI agent (15+ capabilities)
media/
  audio_engine.py       TTS, binaural beats, ambient pads
  video_engine.py       Animated video renderer (MoviePy)
ui/
  theme.py              Dungeon-academic CSS theme and widgets
pages/
  01_Library.py         Course browsing and import
  02_Lecture_Studio.py  Lecture playback and rendering
  03_Professor_AI.py    AI advisor (6 tabs)
  04_Timeline_Editor.py Scene reordering
  05_Batch_Render.py    Batch render queue
  06_Grades.py          GPA, transcript, degrees
  07_Achievements.py    Badge gallery, XP history
  08_Settings.py        All configuration
  09_Diagnostics.py     System health checks
  10_Help.py            Comprehensive help
  11_LLM_Setup.py       Provider setup wizard
schemas/
  course_schema.json    Example course JSON (give to any LLM)
  course_validation_schema.json  JSON Schema for import validation
  SCHEMA_GUIDE.md       Prompt guide for LLM course generation
checklists/             Development roadmap and tracking
```

## Manual Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (pick your OS)
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from core.database import init_db; init_db()"

# Generate pipeline files from notes.txt
python generate_assets.py

# Launch
streamlit run app.py
```

## Troubleshooting

**Python not found**: Make sure Python 3.9+ is installed and added to PATH. On Windows, reinstall Python and check "Add Python to PATH".

**pip install fails**: Try upgrading pip first: `python -m pip install --upgrade pip`. On Linux you may need `python3-venv`: `sudo apt install python3-venv`.

**Streamlit won't start**: Make sure the virtual environment is activated. Check that `streamlit` installed: `pip show streamlit`.

**No audio / TTS fails**: The app uses `edge-tts` (requires internet for first use) with `pyttsx3` as a fallback. On Linux, pyttsx3 needs espeak: `sudo apt install espeak`.

**Video render fails**: FFmpeg is bundled via `imageio-ffmpeg` -- no system install needed. If issues persist, check `pip show imageio-ffmpeg`.

**LLM not responding**: Use the LLM Setup Wizard (page 11) or Diagnostics (page 9) to test connectivity. For local models, make sure Ollama or LM Studio is running.

## Requirements

- Python 3.9+
- Internet connection (for TTS and cloud LLM providers)
- 8GB+ RAM recommended for local LLM models
- All other dependencies installed automatically via `requirements.txt`

## License

This project is provided as-is for educational purposes.
