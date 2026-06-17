"""Sprint 16 — admin course create / delete."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.models.embedding import Embedding
from app.models.enrollment import Enrollment
from app.models.submission import Submission

_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,80}$")
PROTECTED_COURSE_SLUGS = frozenset({"ai-driven-dev", "ai-era-se"})
DEFAULT_PHASE_COUNT = 4

_DEFAULT_PHASE_TITLE = "新しい Phase"
_DEFAULT_PHASE_GOAL = "目標を入力してください。"
_DEFAULT_SYSTEM_PROMPT = (
    "あなたは教育AIチューターです。\n研修生の質問に3〜5文程度の日本語で答えてください。"
)
_DEFAULT_TASK_TITLE = "新しい Task"
_DEFAULT_TASK_DESCRIPTION = "説明を入力してください。"


class CourseSlugInvalidError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"invalid course slug: {slug!r}")
        self.slug = slug


class CourseSlugExistsError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course slug already exists: {slug!r}")
        self.slug = slug


class ProtectedCourseError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"protected course cannot be deleted: {slug!r}")
        self.slug = slug


class CourseHasEnrollmentsError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course {slug!r} has enrollments")
        self.slug = slug


class CourseHasSubmissionsError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course {slug!r} has submissions")
        self.slug = slug


class CourseNotFoundError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course not found: {slug!r}")
        self.slug = slug


@dataclass(frozen=True)
class CourseCreateResult:
    slug: str
    title: str
    description: str | None
    sort_order: int
    phase_count: int
    created_at: datetime


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise CourseSlugInvalidError(slug)


async def _get_course_or_raise(db: AsyncSession, slug: str) -> Course:
    row = (await db.execute(select(Course).where(Course.slug == slug))).scalar_one_or_none()
    if row is None:
        raise CourseNotFoundError(slug)
    return row


async def add_course(
    db: AsyncSession,
    *,
    slug: str,
    title: str,
    description: str | None = None,
) -> CourseCreateResult:
    """新規 course + 4 phase × 1 task の最小 scaffold を作成する。"""
    _validate_slug(slug)
    existing = (await db.execute(select(Course.id).where(Course.slug == slug))).scalar_one_or_none()
    if existing is not None:
        raise CourseSlugExistsError(slug)

    max_sort = (
        await db.execute(select(func.coalesce(func.max(Course.sort_order), -1)))
    ).scalar_one()

    course = Course(
        slug=slug,
        title=title,
        description=description,
        sort_order=max_sort + 1,
    )
    db.add(course)
    await db.flush()

    now = datetime.now(UTC)
    for phase_no in range(1, DEFAULT_PHASE_COUNT + 1):
        phase = CurriculumPhase(
            course_id=course.id,
            phase_no=phase_no,
            title=f"{_DEFAULT_PHASE_TITLE} {phase_no}",
            goal=_DEFAULT_PHASE_GOAL,
            system_prompt=_DEFAULT_SYSTEM_PROMPT,
            updated_at=now,
        )
        db.add(phase)
        await db.flush()
        db.add(
            CurriculumTask(
                phase_id=phase.id,
                task_no=1,
                title=_DEFAULT_TASK_TITLE,
                description=_DEFAULT_TASK_DESCRIPTION,
                skill_tags=[],
                deliverable=None,
                week_label=None,
                updated_at=now,
            )
        )

    await db.flush()
    return CourseCreateResult(
        slug=course.slug,
        title=course.title,
        description=course.description,
        sort_order=course.sort_order,
        phase_count=DEFAULT_PHASE_COUNT,
        created_at=course.created_at,
    )


async def delete_course(db: AsyncSession, *, slug: str) -> None:
    """course と curriculum を削除。enrollment / submission がある場合は拒否。"""
    if slug in PROTECTED_COURSE_SLUGS:
        raise ProtectedCourseError(slug)

    course = await _get_course_or_raise(db, slug)

    enroll_count = (
        await db.execute(
            select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course.id)
        )
    ).scalar_one()
    if enroll_count > 0:
        raise CourseHasEnrollmentsError(slug)

    sub_count = (
        await db.execute(
            select(func.count()).select_from(Submission).where(Submission.course_id == course.id)
        )
    ).scalar_one()
    if sub_count > 0:
        raise CourseHasSubmissionsError(slug)

    phase_ids = (
        (await db.execute(select(CurriculumPhase.id).where(CurriculumPhase.course_id == course.id)))
        .scalars()
        .all()
    )

    if phase_ids:
        await db.execute(delete(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids)))
        await db.execute(delete(CurriculumPhase).where(CurriculumPhase.id.in_(phase_ids)))

    await db.execute(delete(Embedding).where(Embedding.course_id == course.id))
    await db.execute(delete(Course).where(Course.id == course.id))
    await db.flush()
