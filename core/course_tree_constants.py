"""Shared constants and table bootstrap for course tree features."""
from __future__ import annotations

# Carnegie Unit: 1 credit = 15 contact hours + 30 study hours = 45 total hours
CREDIT_HOUR_RATIO = 45

# AI policy levels for assignments
AI_POLICY_LEVELS = ("unrestricted", "assisted", "supervised", "prohibited")

# Bloom's taxonomy competency levels
BLOOMS_LEVELS = ("recall", "understanding", "application", "analysis", "synthesis", "evaluation")

# Pacing options
PACING_OPTIONS = ("fast", "standard", "slow")

_DEFAULT_BENCHMARKS: list[tuple[str, str, str, str, str, float, float, str]] = [
    # (id, name, description, school_ref, required_courses_json, min_gpa, min_hours, category)
    ("mit_6006", "Equivalent to MIT 6.006 (Intro to Algorithms)",
     "Covers sorting, searching, graph algorithms, dynamic programming, and complexity analysis.",
     "MIT", '["junior_cs301"]', 3.0, 135, "computer_science"),
    ("mit_6045", "Equivalent to MIT 6.045 (Automata & Complexity)",
     "Covers automata theory, computability, complexity classes, and cryptographic foundations.",
     "MIT", '["doctoral_cs600"]', 3.0, 135, "computer_science"),
    ("stanford_cs229", "Equivalent to Stanford CS229 (Machine Learning)",
     "Covers supervised/unsupervised learning, neural networks, and deep learning.",
     "Stanford", '["senior_cs450", "doctoral_cs610"]', 3.0, 270, "computer_science"),
    ("stanford_cs161", "Equivalent to Stanford CS161 (Algorithms)",
     "Covers algorithm design, analysis, sorting, graph algorithms, and NP-completeness.",
     "Stanford", '["junior_cs301"]', 3.0, 135, "computer_science"),
    ("comptia_aplus", "CompTIA A+ Equivalent",
     "Hardware, software, networking, and troubleshooting fundamentals.",
     "CompTIA", '["freshman_cs101"]', 2.5, 90, "certification"),
    ("harvard_cs50", "Equivalent to Harvard CS50 (Intro to CS)",
     "Covers abstraction, algorithms, data structures, web development, and software engineering.",
     "Harvard", '["freshman_cs101", "sophomore_cs201"]', 3.0, 200, "computer_science"),
]


def create_tables(tx_func) -> None:
    """Create course-tree, benchmark, and competency tables."""
    with tx_func() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS competency_benchmarks (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                description     TEXT,
                school_ref      TEXT,
                required_courses TEXT,
                min_gpa         REAL DEFAULT 3.0,
                min_hours       REAL DEFAULT 0,
                category        TEXT DEFAULT 'academic',
                created_at      REAL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS qualification_progress (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                benchmark_id    TEXT NOT NULL,
                status          TEXT DEFAULT 'locked',
                progress_pct    REAL DEFAULT 0,
                earned_at       REAL,
                updated_at      REAL DEFAULT (unixepoch()),
                FOREIGN KEY (benchmark_id) REFERENCES competency_benchmarks(id) ON DELETE CASCADE,
                UNIQUE(benchmark_id)
            );

            CREATE TABLE IF NOT EXISTS study_hours_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id       TEXT NOT NULL,
                hours           REAL NOT NULL,
                activity_type   TEXT DEFAULT 'study',
                notes           TEXT,
                logged_at       REAL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS competency_scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id       TEXT NOT NULL,
                blooms_level    TEXT NOT NULL,
                score           REAL DEFAULT 0,
                max_score       REAL DEFAULT 100,
                assessment_id   TEXT,
                updated_at      REAL DEFAULT (unixepoch()),
                UNIQUE(course_id, blooms_level, assessment_id)
            );
        """)


def seed_benchmarks(tx_func) -> None:
    """Seed default qualification benchmarks."""
    with tx_func() as con:
        for bid, name, desc, school, req, gpa, hrs, cat in _DEFAULT_BENCHMARKS:
            con.execute(
                "INSERT OR IGNORE INTO competency_benchmarks "
                "(id, name, description, school_ref, required_courses, min_gpa, min_hours, category) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (bid, name, desc, school, req, gpa, hrs, cat),
            )
