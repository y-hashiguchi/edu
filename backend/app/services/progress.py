"""Progress domain service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import CURRICULUM
from app.models.progress import Progress, ProgressStatus
from app.models.submission import Submission


class PhaseLockedError(Exception):
    def __init__(self, phase: int) -> None:
        super().__init__(f"phase {phase} is locked")
        self.phase = phase


class PhaseNotFoundError(Exception):
    def __init__(self, phase: int) -> None:
        super().__init__(f"progress for phase {phase} not found")
        self.phase = phase


async def initialize_progress_for_course(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    phase_numbers: list[int],
) -> None:
    """Seed progress rows for (user, course). The first phase in
    ``phase_numbers`` is unlocked; the rest start LOCKED."""
    now = datetime.now(UTC)
    sorted_phases = sorted(phase_numbers)
    for i, phase_no in enumerate(sorted_phases):
        is_first = i == 0
        db.add(
            Progress(
                user_id=user_id,
                course_id=course_id,
                phase=phase_no,
                status=(
                    ProgressStatus.IN_PROGRESS.value
                    if is_first
                    else ProgressStatus.LOCKED.value
                ),
                started_at=now if is_first else None,
            )
        )
    await db.flush()


async def initialize_progress(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Legacy single-course shim — enrolls + seeds against DEFAULT_COURSE_SLUG.

    Kept for code paths that still call the old signature. New callers
    should use ``enroll_user`` + ``initialize_progress_for_course`` directly.

    Sprint 7: also auto-enrolls into DEFAULT_COURSE_SLUG so the
    learner can interact with course-scoped routes (dashboard, chat,
    submissions). The enrollment is idempotent — if the user is
    already enrolled, this is a no-op."""
    from app.data.courses import DEFAULT_COURSE_SLUG, get_course
    from app.services.enrollment import (
        AlreadyEnrolledError,
        _get_course_by_slug,
        enroll_user,
    )

    try:
        await enroll_user(db, user_id=user_id, course_slug=DEFAULT_COURSE_SLUG)
    except AlreadyEnrolledError:
        pass
    course_data = get_course(DEFAULT_COURSE_SLUG)
    db_course = await _get_course_by_slug(db, DEFAULT_COURSE_SLUG)
    phase_numbers = [p.phase for p in course_data.phases]
    await initialize_progress_for_course(
        db, user_id, db_course.id, phase_numbers
    )


async def list_progress(db: AsyncSession, user_id: uuid.UUID) -> list[Progress]:
    result = await db.execute(
        select(Progress).where(Progress.user_id == user_id).order_by(Progress.phase)
    )
    return list(result.scalars().all())


async def _get(db: AsyncSession, user_id: uuid.UUID, phase: int) -> Progress | None:
    result = await db.execute(
        select(Progress).where(Progress.user_id == user_id, Progress.phase == phase)
    )
    return result.scalar_one_or_none()


async def is_phase_unlocked(db: AsyncSession, user_id: uuid.UUID, phase: int) -> bool:
    p = await _get(db, user_id, phase)
    return p is not None and p.status != ProgressStatus.LOCKED.value


async def complete_phase(
    db: AsyncSession, user_id: uuid.UUID, phase: int
) -> tuple[Progress, Progress | None]:
    """Mark phase completed; if next phase is locked, unlock it.

    Returns (current, next_unlocked_or_None). Idempotent: re-calling on an
    already-completed phase succeeds with next_unlocked=None.
    """
    current = await _get(db, user_id, phase)
    if current is None:
        raise PhaseNotFoundError(phase)
    if current.status == ProgressStatus.LOCKED.value:
        raise PhaseLockedError(phase)

    now = datetime.now(UTC)
    if current.status != ProgressStatus.COMPLETED.value:
        current.status = ProgressStatus.COMPLETED.value
        current.completed_at = now

    next_unlocked: Progress | None = None
    next_phase = phase + 1
    if next_phase in CURRICULUM:
        nxt = await _get(db, user_id, next_phase)
        if nxt is not None and nxt.status == ProgressStatus.LOCKED.value:
            nxt.status = ProgressStatus.IN_PROGRESS.value
            nxt.started_at = now
            next_unlocked = nxt

    await db.commit()
    return current, next_unlocked


async def maybe_mark_submitted(
    db: AsyncSession, user_id: uuid.UUID, phase: int, required_task_count: int
) -> Progress | None:
    """Promote in_progress -> submitted iff all tasks in phase have a submission."""
    progress = await _get(db, user_id, phase)
    if progress is None or progress.status != ProgressStatus.IN_PROGRESS.value:
        return None
    rows = (
        await db.execute(
            select(Submission.task_no).where(
                Submission.user_id == user_id, Submission.phase == phase
            )
        )
    ).all()
    if len({row.task_no for row in rows}) < required_task_count:
        return None
    progress.status = ProgressStatus.SUBMITTED.value
    await db.flush()
    return progress
