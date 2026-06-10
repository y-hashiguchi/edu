"""Sprint 7 — frozen value objects for the course registry.

These are deliberately frozen to make accidental mutation a TypeError.
Mirror of `Course` ORM model identity (id, slug, title) so the same
fixed UUIDs flow into FK references when the migration seeds the table."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskItem:
    task_no: int
    title: str
    description: str
    skill_tags: tuple[str, ...] = ()
    deliverable: str | None = None
    week_label: str | None = None


@dataclass(frozen=True)
class PhaseData:
    phase: int
    title: str
    goal: str
    tasks: tuple[TaskItem, ...]
    system_prompt: str


@dataclass(frozen=True)
class CourseData:
    id: uuid.UUID
    slug: str
    title: str
    description: str
    sort_order: int
    phases: tuple[PhaseData, ...]
