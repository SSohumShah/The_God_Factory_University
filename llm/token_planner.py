"""Adaptive token-budget planner for course generation.

Given a course's _token_estimate and the active model's profile, computes
exactly how many LLM outputs are needed, broken down by task type (lecture,
assignment, quiz, coding_lab, jargon).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class GenerationTask:
    """A single LLM call in the generation plan."""
    task_type: str          # lecture | assignment | quiz | coding_lab | jargon
    target_id: str          # e.g. "M01-L01", "M01-A01"
    prompt_hint: str        # short description for logging
    estimated_tokens: int   # expected output tokens for this task
    order: int = 0          # execution order


@dataclass
class GenerationPlan:
    """Complete generation plan for a course."""
    course_id: str
    model_family: str
    total_estimated_tokens: int
    usable_output_per_call: int
    tasks: list[GenerationTask] = field(default_factory=list)

    @property
    def total_outputs(self) -> int:
        return len(self.tasks)

    @property
    def by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self.tasks:
            counts[t.task_type] = counts.get(t.task_type, 0) + 1
        return counts

    def estimated_seconds(self, tokens_per_second: float) -> float:
        total_tokens = sum(t.estimated_tokens for t in self.tasks)
        return total_tokens / max(tokens_per_second, 0.1)


def compute_usable_output(max_output_tokens: int, overhead_tokens: int = 500) -> int:
    """Tokens available for content per LLM call."""
    return max(max_output_tokens - overhead_tokens, 256)


def plan_course_generation(
    course: dict,
    max_output_tokens: int,
    chunk_token_target: int,
    overhead_tokens: int = 500,
    model_family: str = "generic",
) -> GenerationPlan:
    """Build a GenerationPlan for a course given model constraints.

    Each generation task type gets its own dedicated LLM output:
    - 1 output per lecture (content generation)
    - 1 output per assignment
    - 1 output per quiz
    - 1 output per coding_lab
    - 1 output for jargon extraction per module
    """
    usable = compute_usable_output(max_output_tokens, overhead_tokens)
    cid = course.get("course_id", "COURSE")
    token_est = course.get("_token_estimate", {})
    total_tokens = token_est.get("total_tokens", 2_000_000)

    tasks: list[GenerationTask] = []
    order = 0

    # Tokens per lecture = total / num_lectures (approximate distribution)
    modules = course.get("modules", [])
    num_lectures = sum(len(m.get("lectures", [])) for m in modules)
    tokens_per_lecture = total_tokens // max(num_lectures, 1)

    # For small models, a single lecture may need multiple outputs
    outputs_per_lecture = max(1, math.ceil(tokens_per_lecture / usable))

    for mod_idx, module in enumerate(modules):
        # One jargon extraction per module
        tasks.append(GenerationTask(
            task_type="jargon",
            target_id=f"{cid}-M{mod_idx + 1}-JARGON",
            prompt_hint=f"Extract terminology for {module.get('title', '')}",
            estimated_tokens=min(usable, chunk_token_target),
            order=order,
        ))
        order += 1

        for lec in module.get("lectures", []):
            lid = lec.get("lecture_id", f"M{mod_idx + 1}-L?")

            # One (or more) output per lecture
            for chunk in range(outputs_per_lecture):
                tasks.append(GenerationTask(
                    task_type="lecture",
                    target_id=f"{lid}-chunk{chunk}" if outputs_per_lecture > 1 else lid,
                    prompt_hint=f"Generate content for {lec.get('title', lid)}",
                    estimated_tokens=min(usable, tokens_per_lecture // outputs_per_lecture),
                    order=order,
                ))
                order += 1

            # Assessment — dedicated output
            if lec.get("assessment"):
                tasks.append(GenerationTask(
                    task_type="quiz",
                    target_id=f"{lid}-QUIZ",
                    prompt_hint=f"Generate quiz for {lec.get('title', lid)}",
                    estimated_tokens=min(usable, chunk_token_target),
                    order=order,
                ))
                order += 1

            # Coding lab — dedicated output
            if lec.get("coding_lab"):
                tasks.append(GenerationTask(
                    task_type="coding_lab",
                    target_id=f"{lid}-LAB",
                    prompt_hint=f"Generate coding lab for {lec.get('title', lid)}",
                    estimated_tokens=min(usable, chunk_token_target),
                    order=order,
                ))
                order += 1

    # Module-level assignment outputs
    for assignment in course.get("assignments", []):
        tasks.append(GenerationTask(
            task_type="assignment",
            target_id=assignment.get("assignment_id", f"{cid}-A?"),
            prompt_hint=f"Generate {assignment.get('title', 'assignment')}",
            estimated_tokens=min(usable, chunk_token_target),
            order=order,
        ))
        order += 1

    return GenerationPlan(
        course_id=cid,
        model_family=model_family,
        total_estimated_tokens=total_tokens,
        usable_output_per_call=usable,
        tasks=sorted(tasks, key=lambda t: t.order),
    )


def estimate_generation_time(plan: GenerationPlan, tokens_per_second: float) -> dict:
    """Estimate wall-clock time for a generation plan."""
    total_tokens = sum(t.estimated_tokens for t in plan.tasks)
    seconds = total_tokens / max(tokens_per_second, 0.1)
    return {
        "total_outputs": plan.total_outputs,
        "total_tokens": total_tokens,
        "estimated_seconds": round(seconds, 1),
        "estimated_minutes": round(seconds / 60, 1),
        "by_type": plan.by_type,
    }


def quick_token_credit_estimate(num_lectures: int, token_target: int = 50_000) -> dict:
    """Quick token-to-credit estimate for display on course cards.

    Returns dict with token_estimate, credit_value, and label.
    """
    token_estimate = num_lectures * token_target
    credit_value = max(1, round(token_estimate / 50_000))
    if token_estimate < 100_000:
        label = f"~{token_estimate // 1000}k tok → {credit_value} cr"
    else:
        label = f"~{token_estimate / 1_000_000:.1f}M tok → {credit_value} cr"
    return {
        "token_estimate": token_estimate,
        "credit_value": credit_value,
        "label": label,
    }
