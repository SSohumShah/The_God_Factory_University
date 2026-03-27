"""Public course-tree facade over focused domain modules."""
from __future__ import annotations

from core.course_tree_competency import (
    check_mastery,
    get_competency_profile,
    record_competency_score,
)
from core.course_tree_constants import (
    AI_POLICY_LEVELS,
    BLOOMS_LEVELS,
    CREDIT_HOUR_RATIO,
    PACING_OPTIONS,
    create_tables,
    seed_benchmarks,
)
from core.course_tree_policy import (
    AI_POLICY_DEFAULTS,
    get_assignment_ai_policy,
    get_default_ai_policy,
)
from core.course_tree_qualifications import (
    check_qualifications,
    get_all_benchmarks,
    get_benchmark_comparison,
    get_qualification_roadmap,
    get_qualifications,
)
from core.course_tree_queries import (
    course_completion_pct,
    course_credit_hours,
    get_child_courses,
    get_course_depth,
    get_course_tree,
    get_root_course,
    get_study_hours,
    hours_to_credits,
    log_study_hours,
)

# Re-export decomposition helpers through the original import surface.
from core.decomposition import (
    PACING_TEMPLATES,
    build_decomposition_prompt,
    build_jargon_prompt,
    build_verification_prompt,
    get_pacing_for_course,
    register_sub_courses,
)

__all__ = [
    "create_tables",
    "seed_benchmarks",
    "CREDIT_HOUR_RATIO",
    "AI_POLICY_LEVELS",
    "BLOOMS_LEVELS",
    "PACING_OPTIONS",
    "get_child_courses",
    "get_course_tree",
    "get_course_depth",
    "get_root_course",
    "course_completion_pct",
    "course_credit_hours",
    "hours_to_credits",
    "log_study_hours",
    "get_study_hours",
    "get_all_benchmarks",
    "check_qualifications",
    "get_qualifications",
    "get_qualification_roadmap",
    "get_benchmark_comparison",
    "AI_POLICY_DEFAULTS",
    "get_default_ai_policy",
    "get_assignment_ai_policy",
    "record_competency_score",
    "get_competency_profile",
    "check_mastery",
    "PACING_TEMPLATES",
    "get_pacing_for_course",
    "build_decomposition_prompt",
    "build_jargon_prompt",
    "build_verification_prompt",
    "register_sub_courses",
]
