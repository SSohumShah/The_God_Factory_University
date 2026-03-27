"""Plan-aware generation queue — sequential/batch LLM executor.

Consumes a GenerationPlan and executes tasks through the Professor
workflow system, supporting progress callbacks, retry, and resume.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable

from llm.token_planner import GenerationPlan, GenerationTask


@dataclass
class TaskResult:
    """Result of a single generation task."""
    task: GenerationTask
    success: bool
    output: str = ""
    error: str = ""
    elapsed_s: float = 0.0


@dataclass
class QueueProgress:
    """Running progress state for the queue."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_task: str = ""
    elapsed_s: float = 0.0


@dataclass
class GenerationQueue:
    """Plan-aware sequential/batch executor for LLM generation tasks.

    Usage:
        queue = GenerationQueue(plan, llm_call_fn)
        results = queue.execute(progress_callback=my_callback)
    """
    plan: GenerationPlan
    llm_call: Callable[[str, str], str]  # (task_type, prompt) -> output
    max_retries: int = 3
    retry_delay: float = 2.0
    batch_size: int = 1  # 1 = sequential, >1 = batch for large-context models
    results: list[TaskResult] = field(default_factory=list)
    _resume_from: int = 0

    def execute(
        self,
        progress_callback: Callable[[QueueProgress], None] | None = None,
    ) -> list[TaskResult]:
        """Execute all tasks in the plan sequentially."""
        tasks = self.plan.tasks[self._resume_from:]
        progress = QueueProgress(total=len(self.plan.tasks), completed=self._resume_from)
        t0 = time.time()

        for task in tasks:
            progress.current_task = f"{task.task_type}: {task.target_id}"
            if progress_callback:
                progress.elapsed_s = time.time() - t0
                progress_callback(progress)

            result = self._execute_task(task)
            self.results.append(result)

            if result.success:
                progress.completed += 1
            else:
                progress.failed += 1

        progress.current_task = "Complete"
        progress.elapsed_s = time.time() - t0
        if progress_callback:
            progress_callback(progress)

        return self.results

    def _execute_task(self, task: GenerationTask) -> TaskResult:
        """Execute a single task with retry logic."""
        last_error = ""
        t0 = time.time()

        for attempt in range(self.max_retries):
            try:
                prompt = self._build_prompt(task)
                output = self.llm_call(task.task_type, prompt)
                return TaskResult(
                    task=task,
                    success=True,
                    output=output,
                    elapsed_s=time.time() - t0,
                )
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        return TaskResult(
            task=task,
            success=False,
            error=last_error,
            elapsed_s=time.time() - t0,
        )

    def _build_prompt(self, task: GenerationTask) -> str:
        """Build the LLM prompt for a generation task."""
        prompts = {
            "lecture": (
                f"Generate detailed lecture content for {task.target_id}.\n"
                f"Task: {task.prompt_hint}\n"
                f"Output as structured JSON with: title, content_sections, "
                f"key_takeaways, examples.\n"
                f"Target approximately {task.estimated_tokens} tokens of content."
            ),
            "quiz": (
                f"Generate a quiz for {task.target_id}.\n"
                f"Task: {task.prompt_hint}\n"
                f"Output as JSON with: questions[] (each with prompt, "
                f"question_type, choices, correct_answer, points).\n"
                f"Generate 5 questions mixing multiple_choice, true_false, "
                f"and short_answer types."
            ),
            "assignment": (
                f"Generate an assignment for {task.target_id}.\n"
                f"Task: {task.prompt_hint}\n"
                f"Output as JSON matching the assignment schema with: "
                f"title, description, rubric[], questions[]."
            ),
            "coding_lab": (
                f"Generate a coding lab exercise for {task.target_id}.\n"
                f"Task: {task.prompt_hint}\n"
                f"Output as JSON with: language, task_description, "
                f"starter_code, test_cases[], expected_output."
            ),
            "jargon": (
                f"Extract key terminology for {task.target_id}.\n"
                f"Task: {task.prompt_hint}\n"
                f"Output as JSON with: terms[] (each with term, definition, "
                f"etymology, usage_example, related_terms[])."
            ),
        }
        return prompts.get(task.task_type, f"Generate content for {task.target_id}: {task.prompt_hint}")

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    def resume_from_last_success(self) -> None:
        """Set resume point to continue after the last successful task."""
        self._resume_from = self.success_count
        self.results = self.results[:self._resume_from]

    def summary(self) -> dict:
        """Return execution summary."""
        return {
            "total_tasks": len(self.plan.tasks),
            "completed": self.success_count,
            "failed": self.failure_count,
            "by_type": self.plan.by_type,
            "total_elapsed_s": sum(r.elapsed_s for r in self.results),
        }
