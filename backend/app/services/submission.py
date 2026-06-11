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
from app.schemas.grading import GradingResult, GradingResultStatus
from app.services import file_storage_service
from app.services.grading import grade_submission
from app.services.progress import maybe_mark_submitted


class SubmissionPhaseInvalidError(Exception):
    pass


class SubmissionTaskInvalidError(Exception):
    pass


# Sprint 7 aliases preferred by new course-aware callers. The historical
# *Invalid* names remain for backwards compatibility with existing route
# imports (Task 12 will migrate them).
class PhaseNotFoundError(SubmissionPhaseInvalidError):
    def __init__(self, phase: int) -> None:
        super().__init__(phase)
        self.phase = phase


class TaskNotFoundError(SubmissionTaskInvalidError):
    def __init__(self, phase: int, task_no: int) -> None:
        super().__init__(f"task_no {task_no} not found in phase {phase}")
        self.phase = phase
        self.task_no = task_no


class SubmissionNotFoundError(Exception):
    pass


class RegradeCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"cooldown active; retry in {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


def _validate_phase_and_task(course_slug: str, phase: int, task_no: int) -> str:
    """Course-aware phase/task validation.

    Returns the human task title for prompt construction. Raises
    ``PhaseNotFoundError`` / ``TaskNotFoundError`` (subclasses of the
    legacy *Invalid* names) so existing callers keep working until Task 12
    migrates them."""
    try:
        phase_def = next(
            p for p in get_course(course_slug).phases if p.phase == phase
        )
    except StopIteration:
        raise PhaseNotFoundError(phase) from None
    if task_no < 1 or task_no > len(phase_def.tasks):
        raise TaskNotFoundError(phase, task_no)
    return phase_def.tasks[task_no - 1].title


def _record_attempt(
    db: AsyncSession, submission_id: uuid.UUID, result: GradingResult
) -> GradingAttempt:
    if result.status == GradingResultStatus.GRADED:
        status = GradingStatus.GRADED
    else:
        status = GradingStatus.FAILED
    attempt = GradingAttempt(
        submission_id=submission_id,
        status=status,
        score=result.score,
        feedback=result.feedback,
        error_message=result.error_message,
        model_name=result.model_name,
    )
    db.add(attempt)
    return attempt


def _apply_result_to_submission(
    submission: Submission, result: GradingResult, *, now: datetime
) -> None:
    if result.status == GradingResultStatus.GRADED:
        submission.score = result.score
        submission.ai_feedback = result.feedback
        submission.graded_at = now
    else:
        submission.score = None
        submission.ai_feedback = (
            f"採点エラー: {result.error_message}" if result.error_message else None
        )
        submission.graded_at = now


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
    task_description = _validate_phase_and_task(course_slug, phase, task_no)

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

    files = await file_storage_service.persist_uploads(
        db=db,
        user_id=user_id,
        submission_id=row.id,
        uploads=uploads,
    )

    result = await grade_submission(
        claude=claude,
        task_description=task_description,
        content=content,
        files=files,
    )

    _record_attempt(db, row.id, result)
    _apply_result_to_submission(row, result, now=now)

    phase_def = next(
        p for p in get_course(course_slug).phases if p.phase == phase
    )
    tasks_total = len(phase_def.tasks)
    await maybe_mark_submitted(
        db, user_id, phase, required_task_count=tasks_total, course_id=course_id
    )

    await db.commit()
    await db.refresh(row)
    return row


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
    stmt = select(Submission).where(
        Submission.id == submission_id, Submission.user_id == user_id
    )
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


async def regrade_submission(
    *,
    db: AsyncSession,
    claude: ClaudeClient,
    user_id: uuid.UUID,
    course_slug: str,
    submission_id: uuid.UUID,
) -> GradingAttempt:
    row = await _load_owned_submission(db, user_id, submission_id, lock=True)

    cooldown = settings.regrade_cooldown_seconds
    last_graded = await _latest_graded_attempt(db, row.id)
    if cooldown > 0 and last_graded is not None:
        elapsed = datetime.now(UTC) - last_graded.created_at
        remaining = cooldown - int(elapsed.total_seconds())
        if remaining > 0:
            raise RegradeCooldownError(retry_after_seconds=remaining)

    task_description = _validate_phase_and_task(course_slug, row.phase, row.task_no)
    files = await file_storage_service.list_submission_files(
        db=db, submission_id=row.id
    )

    result = await grade_submission(
        claude=claude,
        task_description=task_description,
        content=row.content,
        files=files,
    )

    now = datetime.now(UTC)
    attempt = _record_attempt(db, row.id, result)
    _apply_result_to_submission(row, result, now=now)
    await db.commit()
    await db.refresh(attempt)
    await db.refresh(row)
    return attempt


async def list_user_submissions(
    db: AsyncSession, user_id: uuid.UUID, phase: int
) -> list[Submission]:
    rows = (
        await db.execute(
            select(Submission)
            .where(Submission.user_id == user_id, Submission.phase == phase)
            .order_by(Submission.task_no)
        )
    ).scalars().all()
    return list(rows)


async def list_grading_history(
    db: AsyncSession, submission_id: uuid.UUID
) -> list[GradingAttempt]:
    rows = (
        await db.execute(
            select(GradingAttempt)
            .where(GradingAttempt.submission_id == submission_id)
            .order_by(GradingAttempt.created_at.desc())
        )
    ).scalars().all()
    return list(rows)
