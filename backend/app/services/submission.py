"""Submission domain service (Sprint 3: files + grading_attempts + regrade;
Sprint 7: course-aware write paths)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.claude_client import ClaudeClient
from app.data.courses import get_course
from app.models.grading_attempt import GradingAttempt, GradingStatus
from app.models.submission import Submission
from app.services import file_storage_service
from app.services.grading import grade_submission
from app.services.progress import maybe_mark_submitted
from app.services.submission_errors import (
    PhaseNotFoundError,
    RegradeCooldownError,
    SubmissionNotFoundError,
    SubmissionPhaseInvalidError,
    SubmissionTaskInvalidError,
    TaskNotFoundError,
)
from app.services.submission_grading import (
    apply_grading_result,
    grade_submission_by_id,
    record_grading_attempt,
)
from app.services.submission_validate import validate_phase_and_task as _validate_phase_and_task
from app.worker.enqueue import enqueue_grading

__all__ = [
    "PhaseNotFoundError",
    "RegradeCooldownError",
    "SubmissionNotFoundError",
    "SubmissionPhaseInvalidError",
    "SubmissionTaskInvalidError",
    "TaskNotFoundError",
    "list_grading_history",
    "list_user_submissions",
    "regrade_submission",
    "regrade_submission_async",
    "upsert_and_enqueue",
    "upsert_and_grade",
    "upsert_submission",
]


async def upsert_submission(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
    phase: int,
    task_no: int,
    content: str,
    uploads: list[tuple[str, bytes]],
) -> Submission:
    """Persist submission + files. Does not grade."""
    _validate_phase_and_task(course_slug, phase, task_no)

    existing = (
        await db.execute(
            select(Submission).where(
                Submission.user_id == user_id,
                Submission.course_id == course_id,
                Submission.phase == phase,
                Submission.task_no == task_no,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if existing is None:
        row = Submission(
            user_id=user_id,
            course_id=course_id,
            phase=phase,
            task_no=task_no,
            content=content,
            submitted_at=now,
        )
        db.add(row)
        await db.flush()
    else:
        row = existing
        row.content = content
        row.submitted_at = now
        row.ai_feedback = None
        row.score = None
        row.graded_at = None
        await file_storage_service.clear_existing_files(
            db=db, user_id=user_id, submission_id=row.id
        )
        await db.flush()

    await file_storage_service.persist_uploads(
        db=db,
        user_id=user_id,
        submission_id=row.id,
        uploads=uploads,
    )

    phase_def = next(p for p in get_course(course_slug).phases if p.phase == phase)
    await maybe_mark_submitted(
        db, user_id, phase, required_task_count=len(phase_def.tasks), course_id=course_id
    )
    return row


async def upsert_and_enqueue(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
    phase: int,
    task_no: int,
    content: str,
    uploads: list[tuple[str, bytes]],
) -> Submission:
    """Sprint 8: persist immediately, grade in background."""
    row = await upsert_submission(
        db=db,
        user_id=user_id,
        course_id=course_id,
        course_slug=course_slug,
        phase=phase,
        task_no=task_no,
        content=content,
        uploads=uploads,
    )
    await db.commit()
    await db.refresh(row)
    await enqueue_grading(row.id)
    await db.refresh(row)
    return row


async def upsert_and_grade(
    *,
    db: AsyncSession,
    claude: ClaudeClient,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
    phase: int,
    task_no: int,
    content: str,
    uploads: list[tuple[str, bytes]],
) -> Submission:
    """Synchronous grading path (GRADING_ASYNC_ENABLED=false)."""
    row = await upsert_submission(
        db=db,
        user_id=user_id,
        course_id=course_id,
        course_slug=course_slug,
        phase=phase,
        task_no=task_no,
        content=content,
        uploads=uploads,
    )
    await db.flush()
    graded = await grade_submission_by_id(db, claude, row.id)
    assert graded is not None
    await db.commit()
    await db.refresh(graded)
    return graded


async def _latest_graded_attempt(
    db: AsyncSession, submission_id: uuid.UUID
) -> GradingAttempt | None:
    return (
        await db.execute(
            select(GradingAttempt)
            .where(
                GradingAttempt.submission_id == submission_id,
                GradingAttempt.status == GradingStatus.GRADED,
            )
            .order_by(GradingAttempt.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _load_owned_submission(
    db: AsyncSession,
    user_id: uuid.UUID,
    submission_id: uuid.UUID,
    *,
    lock: bool = False,
) -> Submission:
    stmt = select(Submission).where(Submission.id == submission_id, Submission.user_id == user_id)
    if lock:
        # SELECT ... FOR UPDATE serialises concurrent regrade requests on the
        # same submission. Without this, two parallel cooldown checks can both
        # read a "cooldown expired" state and both proceed to call Claude,
        # bypassing the rate limit and burning N× the API cost.
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise SubmissionNotFoundError(str(submission_id))
    return row


async def _check_regrade_cooldown(db: AsyncSession, submission: Submission) -> None:
    """Raise RegradeCooldownError if the most recent graded attempt is
    inside the cooldown window. Shared by sync + async regrade paths."""
    cooldown = settings.regrade_cooldown_seconds
    if cooldown <= 0:
        return
    last_graded = await _latest_graded_attempt(db, submission.id)
    if last_graded is None:
        return
    elapsed = datetime.now(UTC) - last_graded.created_at
    remaining = cooldown - int(elapsed.total_seconds())
    if remaining > 0:
        raise RegradeCooldownError(retry_after_seconds=remaining)


async def regrade_submission(
    *,
    db: AsyncSession,
    claude: ClaudeClient,
    user_id: uuid.UUID,
    course_slug: str,
    submission_id: uuid.UUID,
) -> GradingAttempt:
    """Synchronous regrade path (used when GRADING_ASYNC_ENABLED=false)."""
    row = await _load_owned_submission(db, user_id, submission_id, lock=True)
    await _check_regrade_cooldown(db, row)

    task_description = _validate_phase_and_task(course_slug, row.phase, row.task_no)
    files = await file_storage_service.list_submission_files(db=db, submission_id=row.id)

    result = await grade_submission(
        claude=claude,
        task_description=task_description,
        content=row.content,
        files=files,
    )

    now = datetime.now(UTC)
    attempt = record_grading_attempt(db, row.id, result)
    apply_grading_result(row, result, now=now)
    await db.commit()
    await db.refresh(attempt)
    await db.refresh(row)
    return attempt


async def regrade_submission_async(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    course_slug: str,
    submission_id: uuid.UUID,
) -> Submission:
    """Sprint 8 follow-up: queue regrade on the arq worker.

    The route still runs the cooldown check and validates the phase/task
    synchronously so the client sees the error path immediately. Once
    queued, ``submission.graded_at`` is reset to ``None`` so the
    frontend's poll loop can distinguish "freshly queued for regrade"
    from "already graded by a previous attempt"."""
    row = await _load_owned_submission(db, user_id, submission_id, lock=True)
    await _check_regrade_cooldown(db, row)
    # Validate phase/task here so a misconfigured course surfaces a
    # 422/404 instead of a worker-side crash.
    _validate_phase_and_task(course_slug, row.phase, row.task_no)

    row.graded_at = None
    await db.commit()
    await db.refresh(row)
    await enqueue_grading(row.id)
    await db.refresh(row)
    return row


async def list_user_submissions(
    db: AsyncSession, user_id: uuid.UUID, phase: int
) -> list[Submission]:
    rows = (
        (
            await db.execute(
                select(Submission)
                .where(Submission.user_id == user_id, Submission.phase == phase)
                .order_by(Submission.task_no)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def list_grading_history(db: AsyncSession, submission_id: uuid.UUID) -> list[GradingAttempt]:
    rows = (
        (
            await db.execute(
                select(GradingAttempt)
                .where(GradingAttempt.submission_id == submission_id)
                .order_by(GradingAttempt.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)
