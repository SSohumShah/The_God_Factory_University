"""Assignment AI policy defaults and resolution helpers."""
from __future__ import annotations

import json

# Default AI policies per assignment type / subject
AI_POLICY_DEFAULTS: dict[str, dict] = {
    "exam": {
        "level": "prohibited",
        "allowed_uses": [],
        "prohibited_uses": ["all"],
        "verification_type": "none",
    },
    "quiz": {
        "level": "prohibited",
        "allowed_uses": [],
        "prohibited_uses": ["all"],
        "verification_type": "none",
    },
    "homework": {
        "level": "assisted",
        "allowed_uses": ["research", "grammar_check", "code_debugging"],
        "prohibited_uses": ["direct_answers", "essay_generation"],
        "verification_type": "original_example",
    },
    "project": {
        "level": "supervised",
        "allowed_uses": ["research", "scaffolding", "debugging"],
        "prohibited_uses": ["complete_solutions"],
        "verification_type": "oral_explanation",
    },
    "lab": {
        "level": "supervised",
        "allowed_uses": ["debugging", "documentation_lookup"],
        "prohibited_uses": ["complete_implementations"],
        "verification_type": "original_example",
    },
    "verification": {
        "level": "prohibited",
        "allowed_uses": [],
        "prohibited_uses": ["all"],
        "verification_type": "none",
    },
}


def get_default_ai_policy(assignment_type: str) -> dict:
    """Get the default AI policy for a given assignment type."""
    return AI_POLICY_DEFAULTS.get(assignment_type, AI_POLICY_DEFAULTS["homework"])


def get_assignment_ai_policy(assignment: dict) -> dict:
    """Get assignment AI policy from stored payload or defaults."""
    stored = assignment.get("ai_policy")
    if stored:
        if isinstance(stored, str):
            try:
                return json.loads(stored)
            except (json.JSONDecodeError, ValueError):
                pass
        elif isinstance(stored, dict):
            return stored
    return get_default_ai_policy(assignment.get("type", "homework"))
