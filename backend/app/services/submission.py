"""Submission domain service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claude_client import ClaudeClient
from app.data.curriculum import CURRICULUM
from app.models.submission import Submission
from app.schemas.grading import GradingResult, GradingResultStatus
from app.services.grading import grade_submission
from app.services.progress import maybe_mark_submitted


class SubmissionPhaseInvalidError(Exception):
    pass


class SubmissionTaskInvalidError(Exception):
    pass


async def upsert_and_grade(
    *,
    db: AsyncSession,
    claude: ClaudeClient,
    user_id: uuid.UUID,
    phase: int,
    task_no: int,
    content: str,
) -> Submission:
    if phase not in CURRICULUM:
        raise SubmissionPhaseInvalidError(phase)
    tasks = CURRICULUM[phase]["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise SubmissionTaskInvalidError(task_no)
    task_description = tasks[task_no - 1]

    existing = (
        await db.execute(
            select(Submission).where(
                Submission.user_id == user_id,
                Submission.phase == phase,
                Submission.task_no == task_no,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if existing is None:
        row = Submission(
            user_id=user_id,
            phase=phase,
            task_no=task_no,
            content=content,
            submitted_at=now,
        )
        db.add(row)
    else:
        row = existing
        row.content = content
        row.submitted_at = now
        row.ai_feedback = None
        row.score = None
        row.graded_at = None

    await db.flush()

    result: GradingResult = await grade_submission(
        claude=claude, task_description=task_description, content=content, files=[]
    )
    if result.status == GradingResultStatus.GRADED:
        row.score = result.score
        row.ai_feedback = result.feedback
    else:
        row.ai_feedback = f"採点エラー: {result.error_message}"
        row.score = None
    row.graded_at = now

    await maybe_mark_submitted(db, user_id, phase, required_task_count=len(tasks))

    await db.commit()
    return row


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
