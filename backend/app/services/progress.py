"""Progress domain service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import CURRICULUM
from app.models.progress import Progress, ProgressStatus


class PhaseLockedError(Exception):
    def __init__(self, phase: int) -> None:
        super().__init__(f"phase {phase} is locked")
        self.phase = phase


class PhaseNotFoundError(Exception):
    def __init__(self, phase: int) -> None:
        super().__init__(f"progress for phase {phase} not found")
        self.phase = phase


async def initialize_progress(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Seed progress rows for a freshly-created user."""
    now = datetime.now(UTC)
    for phase_no in sorted(CURRICULUM.keys()):
        is_first = phase_no == 1
        db.add(
            Progress(
                user_id=user_id,
                phase=phase_no,
                status=(
                    ProgressStatus.IN_PROGRESS.value if is_first else ProgressStatus.LOCKED.value
                ),
                started_at=now if is_first else None,
            )
        )
    await db.flush()


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
