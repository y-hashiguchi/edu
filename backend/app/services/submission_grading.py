"""Shared grading persistence helpers (sync API + async worker)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claude_client import ClaudeClient
from app.data.courses import get_course
from app.models.course import Course
from app.models.grading_attempt import GradingAttempt, GradingStatus
from app.models.submission import Submission
from app.schemas.grading import GradingResult, GradingResultStatus
from app.services import file_storage_service
from app.services.grading import grade_submission
from app.services.progress import maybe_mark_submitted
from app.services.submission_validate import validate_phase_and_task


def record_grading_attempt(
    db: AsyncSession, submission_id: uuid.UUID, result: GradingResult
) -> GradingAttempt:
    status = (
        GradingStatus.GRADED
        if result.status == GradingResultStatus.GRADED
        else GradingStatus.FAILED
    )
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


def apply_grading_result(submission: Submission, result: GradingResult, *, now: datetime) -> None:
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


async def grade_submission_by_id(
    db: AsyncSession,
    claude: ClaudeClient,
    submission_id: uuid.UUID,
) -> Submission | None:
    row = (
        await db.execute(
            select(Submission, Course)
            .join(Course, Submission.course_id == Course.id)
            .where(Submission.id == submission_id)
        )
    ).one_or_none()
    if row is None:
        return None
    submission, course = row

    task_description = validate_phase_and_task(course.slug, submission.phase, submission.task_no)
    files = await file_storage_service.list_submission_files(db=db, submission_id=submission.id)
    result = await grade_submission(
        claude=claude,
        task_description=task_description,
        content=submission.content,
        files=files,
    )

    now = datetime.now(UTC)
    record_grading_attempt(db, submission.id, result)
    apply_grading_result(submission, result, now=now)

    phase_def = next(p for p in get_course(course.slug).phases if p.phase == submission.phase)
    await maybe_mark_submitted(
        db,
        submission.user_id,
        submission.phase,
        required_task_count=len(phase_def.tasks),
        course_id=submission.course_id,
    )
    return submission
