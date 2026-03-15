# HOW TO GENERATE COURSES WITH AN LLM

## How the 3 Schema Files Work Together

```
course_schema.json          -- LLM template (copy/paste into any LLM prompt)
        |
        v
  LLM fills it in --> JSON output --> Bulk Import (Library page)
        |                                    |
        v                                    v
assignment_schema.json      course_validation_schema.json
(optional: generate              (validates structure
 assignments separately)          before saving to DB)
```

| File | Purpose | Used By |
|------|---------|---------|
| `course_schema.json` | Example template you paste into an LLM prompt | You (the user) |
| `course_validation_schema.json` | JSON Schema (Draft-07) that validates imports | `db_import.py` (automatic) |
| `assignment_schema.json` | JSON Schema for standalone assignment batches | `db_import.py` (automatic) |

---

## The 3-Step Workflow

### Step 1 -- Write your topic request
Think of anything you want to learn. Examples:
- "Quantum mechanics for programmers"
- "History of jazz and music theory"
- "Ethical hacking and penetration testing"
- "Spanish language -- beginner to intermediate"
- "Economics of AI and automation"

### Step 2 -- Send this prompt to any LLM (ChatGPT, Claude, Copilot, Gemini, etc.)

```
Here is a JSON schema for an educational course.
I want you to fill this schema out completely for the topic: [YOUR TOPIC HERE].
Generate [NUMBER] modules with [NUMBER] lectures each.
Make it [beginner / intermediate / advanced] level.
Include realistic narration prompts and visual scene descriptions for video generation.
Return ONLY the JSON. No other text.

SCHEMA:
[paste the contents of schemas/course_schema.json here]
```

### Step 3 -- Paste the output into The God Factory University
1. Open the app
2. Go to **Library** page
3. Click **Bulk Import**
4. Paste the JSON (single object, array, or multiple newline-delimited objects)
5. Click **Import**
6. The app validates your JSON against `course_validation_schema.json` automatically
7. Valid courses are stored in the database

---

## Adding Assignments Separately

If your course JSON didn't include assignments, or you want to add more later,
generate a standalone assignment batch using `assignment_schema.json`:

```
Generate assignments for course CS-101 using this JSON schema.
Create a mix of quizzes, homework, and projects.
Return ONLY the JSON. No other text.

SCHEMA:
[paste the contents of schemas/assignment_schema.json here]
```

Paste the result into Bulk Import -- it detects assignment batches automatically.

---

## Bulk Import Tips

- You can paste ONE course JSON, an ARRAY `[{...}, {...}]`, or multiple separate JSONs
- The app detects structure automatically — it handles full courses, lone modules, and single lectures
- Generate 10 courses in a row and paste them all at once
- The Professor AI inside the app can also generate courses directly

---

## Required Fields (minimum viable lecture)
```json
{
  "lecture_id": "unique_id",
  "title": "Lecture Title",
  "video_recipe": {
    "scene_blocks": [
      { "block_id": "A", "duration_s": 90,
        "narration_prompt": "What to say.", "visual_prompt": "What to show." }
    ]
  }
}
```

---

## Video Generation Prompt Packs
Each lecture contains `video_recipe.scene_blocks` with:
- `narration_prompt` — used for TTS voiceover
- `visual_prompt` — used for Runway / Pika / ComfyUI
- `ambiance` — music direction, sfx direction, color palette

The app exports `data/prompt_packs.jsonl` with Runway, Pika, and Comfy-formatted prompts
for every scene in every lecture.

---

## Degree & Credit System

| Degree       | Min Credits | Min GPA |
|--------------|-------------|---------|
| Certificate  | 15          | 2.0     |
| Associate    | 60          | 2.0     |
| Bachelor     | 120         | 2.0     |
| Master       | 150         | 3.0     |
| Doctorate    | 180         | 3.5     |

Each course has a `credits` field (default 3). Complete lectures in that course to count them.

---

## Professor AI — Generate Content Inside the App
The Professor AI page lets you:
- Chat directly with the LLM professor
- Ask it to generate a new course (output goes to Bulk Import queue)
- Request quizzes, homework, study guides, and research rabbit holes
- Have it grade your essays and code
- Get personalized next-topic recommendations
