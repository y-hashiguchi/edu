"""Progress domain service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses import get_course
from app.data.curriculum import CURRICULUM  # noqa: F401 — kept for legacy callers
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
                    ProgressStatus.IN_PROGRESS.value if is_first else ProgressStatus.LOCKED.value
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
    await initialize_progress_for_course(db, user_id, db_course.id, phase_numbers)


async def list_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID | None = None,
) -> list[Progress]:
    """List a user's progress rows, optionally narrowed to one course.

    Sprint 7 MED-1: callers that already resolve a CourseContext should
    pass course_id so the SQL filter happens server-side instead of
    in-route. None preserves the legacy "all courses" shape for callers
    that haven't migrated yet.
    """
    stmt = select(Progress).where(Progress.user_id == user_id)
    if course_id is not None:
        stmt = stmt.where(Progress.course_id == course_id)
    result = await db.execute(stmt.order_by(Progress.phase))
    return list(result.scalars().all())


async def _get(
    db: AsyncSession,
    user_id: uuid.UUID,
    phase: int,
    course_id: uuid.UUID | None = None,
) -> Progress | None:
    stmt = select(Progress).where(Progress.user_id == user_id, Progress.phase == phase)
    if course_id is not None:
        stmt = stmt.where(Progress.course_id == course_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def is_phase_unlocked(
    db: AsyncSession,
    user_id: uuid.UUID,
    phase: int,
    course_id: uuid.UUID | None = None,
) -> bool:
    """Sprint 7 MED-1: optional course_id keeps unlock state separate
    per course. Legacy callers (without course_id) see the union of
    all courses — preserved for backwards compat."""
    p = await _get(db, user_id, phase, course_id=course_id)
    return p is not None and p.status != ProgressStatus.LOCKED.value


async def complete_phase(
    db: AsyncSession,
    user_id: uuid.UUID,
    phase: int,
    course_id: uuid.UUID | None = None,
    course_slug: str | None = None,
) -> tuple[Progress, Progress | None]:
    """Mark phase completed; if next phase is locked, unlock it.

    Returns (current, next_unlocked_or_None). Idempotent: re-calling on an
    already-completed phase succeeds with next_unlocked=None.

    Sprint 7 MED-1: when both course_id and course_slug are provided,
    the next-phase lookup uses the course registry instead of the
    legacy single-course CURRICULUM mapping. Existing single-course
    callers keep working unchanged.
    """
    current = await _get(db, user_id, phase, course_id=course_id)
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

    # Determine whether next_phase exists for the active scope:
    # - course-aware path: ask the registry
    # - legacy path: fall back to the ai-driven-dev CURRICULUM mapping
    if course_slug is not None:
        valid_phases = {p.phase for p in get_course(course_slug).phases}
        next_phase_exists = next_phase in valid_phases
    else:
        next_phase_exists = next_phase in CURRICULUM

    if next_phase_exists:
        nxt = await _get(db, user_id, next_phase, course_id=course_id)
        if nxt is not None and nxt.status == ProgressStatus.LOCKED.value:
            nxt.status = ProgressStatus.IN_PROGRESS.value
            nxt.started_at = now
            next_unlocked = nxt

    await db.commit()
    return current, next_unlocked


async def maybe_mark_submitted(
    db: AsyncSession,
    user_id: uuid.UUID,
    phase: int,
    required_task_count: int,
    course_id: uuid.UUID | None = None,
) -> Progress | None:
    """Promote in_progress -> submitted iff all tasks in phase have a submission.

    Sprint 7 MED-1: course_id narrows both the Progress lookup and the
    Submission count to one course so a learner enrolled in two
    courses with overlapping phase numbers doesn't promote one course
    based on submissions to another.
    """
    progress = await _get(db, user_id, phase, course_id=course_id)
    if progress is None or progress.status != ProgressStatus.IN_PROGRESS.value:
        return None
    stmt = select(Submission.task_no).where(
        Submission.user_id == user_id, Submission.phase == phase
    )
    if course_id is not None:
        stmt = stmt.where(Submission.course_id == course_id)
    rows = (await db.execute(stmt)).all()
    if len({row.task_no for row in rows}) < required_task_count:
        return None
    progress.status = ProgressStatus.SUBMITTED.value
    await db.flush()
    return progress
