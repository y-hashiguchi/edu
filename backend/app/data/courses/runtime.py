"""Sprint 9 — process-local in-memory cache of published curriculum.

The cache is populated from the DB at app startup (`lifespan` in
`app/main.py`) and refreshed after `POST /api/admin/curriculum/{slug}/publish`.

This lets the existing synchronous `get_course(slug)` API stay
unchanged while moving the source of truth from the Python registry to
the DB.

Multi-worker: ``notify_cache_reload`` publishes to Redis after publish;
peer workers reload via ``app.services.curriculum_cache_pubsub`` listener
(see ``curriculum_cache_pubsub_enabled`` in config).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses.types import CourseData, PhaseData, TaskItem
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask


# process-local cache. Cleared by tests via `_CACHE.clear()`.
_CACHE: dict[str, CourseData] = {}


def _build_task(row: CurriculumTask) -> TaskItem:
    return TaskItem(
        task_no=row.task_no,
        title=row.title,
        description=row.description,
        skill_tags=tuple(row.skill_tags or ()),
        deliverable=row.deliverable,
        week_label=row.week_label,
    )


def _build_phase(
    phase_row: CurriculumPhase, task_rows: list[CurriculumTask]
) -> PhaseData:
    tasks = tuple(
        _build_task(t)
        for t in sorted(task_rows, key=lambda r: r.task_no)
    )
    return PhaseData(
        phase=phase_row.phase_no,
        title=phase_row.title,
        goal=phase_row.goal,
        tasks=tasks,
        system_prompt=phase_row.system_prompt,
    )


def _build_course(
    course: Course,
    pairs: list[tuple[CurriculumPhase, list[CurriculumTask]]],
) -> CourseData:
    phases = tuple(
        _build_phase(p, t)
        for p, t in sorted(pairs, key=lambda x: x[0].phase_no)
    )
    return CourseData(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description or "",
        sort_order=course.sort_order,
        phases=phases,
    )


async def _load_course_phases(
    db: AsyncSession, course_id: uuid.UUID
) -> list[tuple[CurriculumPhase, list[CurriculumTask]]]:
    """Return (phase, tasks) pairs for one course."""
    phases = list((await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course_id)
    )).scalars().all())
    if not phases:
        return []
    phase_ids = [p.id for p in phases]
    tasks = list((await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
    )).scalars().all())
    by_phase: dict[uuid.UUID, list[CurriculumTask]] = {pid: [] for pid in phase_ids}
    for t in tasks:
        by_phase[t.phase_id].append(t)
    return [(p, by_phase[p.id]) for p in phases]


async def reload_from_db(db: AsyncSession) -> None:
    """全 course の CourseData を再構築して `_CACHE` を置き換える。

    Sprint 9 / 起動時: app.main.lifespan が 1 度呼ぶ。0 行は明示的なエラー。
    """
    courses = list((await db.execute(select(Course))).scalars().all())
    if not courses:
        raise RuntimeError(
            "curriculum cache: courses table is empty — "
            "alembic upgrade head が未実行の可能性"
        )

    new_cache: dict[str, CourseData] = {}
    for course in courses:
        pairs = await _load_course_phases(db, course.id)
        if not pairs:
            raise RuntimeError(
                f"curriculum_phases is empty for course {course.slug!r} — "
                "alembic seed が未実行の可能性"
            )
        new_cache[course.slug] = _build_course(course, pairs)

    _CACHE.clear()
    _CACHE.update(new_cache)


async def reload_course(db: AsyncSession, slug: str) -> None:
    """1 course だけを再構築して cache を差し替える (publish 後に呼ぶ)。"""
    course = (
        await db.execute(select(Course).where(Course.slug == slug))
    ).scalar_one_or_none()
    if course is None:
        from app.data.courses import CourseNotFoundError
        raise CourseNotFoundError(slug)
    pairs = await _load_course_phases(db, course.id)
    _CACHE[slug] = _build_course(course, pairs)


def evict_course(slug: str) -> None:
    """course 削除後に cache から除去する。"""
    _CACHE.pop(slug, None)


def get_cached_course(slug: str) -> CourseData:
    """同期 API。`get_course(slug)` から呼ばれる。

    cache miss は CourseNotFoundError。reload 漏れの早期検出を狙う。
    """
    from app.data.courses import CourseNotFoundError

    try:
        return _CACHE[slug]
    except KeyError:
        raise CourseNotFoundError(slug) from None
