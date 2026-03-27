"""Public Professor facade over focused Professor mixins."""
from __future__ import annotations

from llm.professor_base import PROFESSOR_SYSTEM, ProfessorBaseMixin, ProfessorResponse
from llm.professor_content import ProfessorContentMixin
from llm.professor_workflows import ProfessorWorkflowMixin


class Professor(ProfessorBaseMixin, ProfessorContentMixin, ProfessorWorkflowMixin):
    """Stable public Professor API composed from focused mixins."""


__all__ = ["Professor", "ProfessorResponse", "PROFESSOR_SYSTEM"]
