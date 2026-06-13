"""Sprint 9 — curriculum edit service.

Routes never touch the ORM directly. They call these helpers and the
service is responsible for:
  - exclude_unset セマンティクス (key in dict / not in dict の判別)
  - publish 時の cache 差し替え
  - エラーハンドリング (PhaseNotFoundError / TaskNotFoundError /
    CourseNotFoundError)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses import CourseNotFoundError
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask


class PhaseNotFoundError(Exception):
    def __init__(self, slug: str, phase_no: int) -> None:
        super().__init__(f"phase {phase_no} not found in course {slug!r}")
        self.slug = slug
        self.phase_no = phase_no


class TaskNotFoundError(Exception):
    def __init__(self, slug: str, phase_no: int, task_no: int) -> None:
        super().__init__(
            f"task {task_no} not found in phase {phase_no} of course {slug!r}"
        )
        self.slug = slug
        self.phase_no = phase_no
        self.task_no = task_no


@dataclass(frozen=True)
class PublishResult:
    slug: str
    published_phase_count: int
    published_task_count: int
    published_at: datetime


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


async def _get_course_by_slug(db: AsyncSession, slug: str) -> Course:
    course = (
        await db.execute(select(Course).where(Course.slug == slug))
    ).scalar_one_or_none()
    if course is None:
        raise CourseNotFoundError(slug)
    return course


async def _get_phase_or_raise(
    db: AsyncSession, course_slug: str, course_id, phase_no: int
) -> CurriculumPhase:
    row = (
        await db.execute(
            select(CurriculumPhase).where(
                CurriculumPhase.course_id == course_id,
                CurriculumPhase.phase_no == phase_no,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise PhaseNotFoundError(course_slug, phase_no)
    return row


async def _get_task_or_raise(
    db: AsyncSession,
    course_slug: str,
    phase_no: int,
    phase_id,
    task_no: int,
) -> CurriculumTask:
    row = (
        await db.execute(
            select(CurriculumTask).where(
                CurriculumTask.phase_id == phase_id,
                CurriculumTask.task_no == task_no,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise TaskNotFoundError(course_slug, phase_no, task_no)
    return row


# ---------------------------------------------------------------------------
# Draft write
# ---------------------------------------------------------------------------


_PHASE_DRAFT_FIELDS = ("title", "goal", "system_prompt")
_TASK_DRAFT_FIELDS = (
    "title",
    "description",
    "skill_tags",
    "deliverable",
    "week_label",
)


async def put_phase_draft(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    payload: Mapping[str, Any],
) -> CurriculumPhase:
    """payload に key があるフィールドだけ draft_* を更新する。

    None 値は「draft をクリア」、明示値は「draft を設定」。key の不在は
    「変更なし」。route は `model_dump(exclude_unset=True)` を渡す。
    """
    course = await _get_course_by_slug(db, course_slug)
    row = await _get_phase_or_raise(db, course_slug, course.id, phase_no)

    for field in _PHASE_DRAFT_FIELDS:
        if field in payload:
            setattr(row, f"draft_{field}", payload[field])
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


async def put_task_draft(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    task_no: int,
    payload: Mapping[str, Any],
) -> CurriculumTask:
    course = await _get_course_by_slug(db, course_slug)
    phase = await _get_phase_or_raise(db, course_slug, course.id, phase_no)
    row = await _get_task_or_raise(db, course_slug, phase_no, phase.id, task_no)

    for field in _TASK_DRAFT_FIELDS:
        if field in payload:
            setattr(row, f"draft_{field}", payload[field])
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# Publish / discard
# ---------------------------------------------------------------------------


async def publish_course(
    db: AsyncSession, *, course_slug: str
) -> PublishResult:
    """全 draft_* を対応する published 列に COPY、draft_* を NULL に。

    Returns: 影響行数。0 件も idempotent (200 OK)。

    Cache invalidation is the route's responsibility — it must call
    ``runtime.reload_course`` *after* ``db.commit()`` so a commit-time
    failure does not leave the cache holding values the DB rolled back.
    """
    course = await _get_course_by_slug(db, course_slug)

    phases = (await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course.id)
    )).scalars().all()

    published_phase = 0
    for p in phases:
        dirty = False
        if p.draft_title is not None:
            p.title = p.draft_title
            p.draft_title = None
            dirty = True
        if p.draft_goal is not None:
            p.goal = p.draft_goal
            p.draft_goal = None
            dirty = True
        if p.draft_system_prompt is not None:
            p.system_prompt = p.draft_system_prompt
            p.draft_system_prompt = None
            dirty = True
        if dirty:
            published_phase += 1
            p.updated_at = datetime.now(UTC)

    phase_ids = [p.id for p in phases]
    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
    )).scalars().all() if phase_ids else []

    published_task = 0
    for t in tasks:
        dirty = False
        if t.draft_title is not None:
            t.title = t.draft_title
            t.draft_title = None
            dirty = True
        if t.draft_description is not None:
            t.description = t.draft_description
            t.draft_description = None
            dirty = True
        if t.draft_skill_tags is not None:
            t.skill_tags = t.draft_skill_tags
            t.draft_skill_tags = None
            dirty = True
        if t.draft_deliverable is not None:
            # 空文字 = "明示的に空にしたい"。published 列を NULL に統一する運用。
            t.deliverable = t.draft_deliverable or None
            t.draft_deliverable = None
            dirty = True
        if t.draft_week_label is not None:
            t.week_label = t.draft_week_label or None
            t.draft_week_label = None
            dirty = True
        if dirty:
            published_task += 1
            t.updated_at = datetime.now(UTC)

    await db.flush()

    return PublishResult(
        slug=course_slug,
        published_phase_count=published_phase,
        published_task_count=published_task,
        published_at=datetime.now(UTC),
    )


async def discard_drafts(db: AsyncSession, *, course_slug: str) -> None:
    """当該 course 配下の全 draft_* 列を NULL にする。published は変更なし。"""
    course = await _get_course_by_slug(db, course_slug)
    phase_id_rows = (await db.execute(
        select(CurriculumPhase.id).where(CurriculumPhase.course_id == course.id)
    )).all()
    phase_ids = [row[0] for row in phase_id_rows]

    await db.execute(
        update(CurriculumPhase)
        .where(CurriculumPhase.course_id == course.id)
        .values(
            draft_title=None,
            draft_goal=None,
            draft_system_prompt=None,
        )
    )
    if phase_ids:
        await db.execute(
            update(CurriculumTask)
            .where(CurriculumTask.phase_id.in_(phase_ids))
            .values(
                draft_title=None,
                draft_description=None,
                draft_skill_tags=None,
                draft_deliverable=None,
                draft_week_label=None,
            )
        )
    await db.flush()


# ---------------------------------------------------------------------------
# Count drafts (admin 一覧バッジ用)
# ---------------------------------------------------------------------------


async def count_pending_drafts(db: AsyncSession, *, course_slug: str) -> int:
    """draft_* に非 NULL がある field の総数を返す (Phase + Task)。"""
    course = await _get_course_by_slug(db, course_slug)
    phases = (await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course.id)
    )).scalars().all()
    n = 0
    for p in phases:
        n += sum(
            1
            for f in ("draft_title", "draft_goal", "draft_system_prompt")
            if getattr(p, f) is not None
        )
    phase_ids = [p.id for p in phases]
    if phase_ids:
        tasks = (await db.execute(
            select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
        )).scalars().all()
        for t in tasks:
            n += sum(
                1
                for f in (
                    "draft_title",
                    "draft_description",
                    "draft_skill_tags",
                    "draft_deliverable",
                    "draft_week_label",
                )
                if getattr(t, f) is not None
            )
    return n
