"""Admin → submissions feed + detail (Sprint 4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminCommentOut,
    AdminSubmissionDetail,
    AdminSubmissionListOut,
    AdminSubmissionSummary,
)
from app.schemas.grading import GradingAttemptOut
from app.schemas.submission import SubmissionFileOut
from app.services import admin_query

router = APIRouter(prefix="/api/admin/submissions", tags=["admin"])


@router.get("", response_model=AdminSubmissionListOut)
async def list_submissions(
    user_id: uuid.UUID | None = Query(default=None),
    phase: int | None = Query(default=None, ge=1, le=4),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminSubmissionListOut:
    rows = await admin_query.list_submissions(
        db, user_id=user_id, phase=phase, limit=limit, offset=offset
    )
    total = await admin_query.count_submissions(
        db, user_id=user_id, phase=phase
    )
    items = [
        AdminSubmissionSummary(
            id=sub.id,
            user_id=user.id,
            user_email=user.email,
            user_name=user.name,
            phase=sub.phase,
            task_no=sub.task_no,
            score=sub.score,
            submitted_at=sub.submitted_at,
            graded_at=sub.graded_at,
        )
        for sub, user in rows
    ]
    return AdminSubmissionListOut(
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{submission_id}", response_model=AdminSubmissionDetail)
async def get_submission(
    submission_id: uuid.UUID,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminSubmissionDetail:
    found = await admin_query.get_submission_detail(db, submission_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="submission not found"
        )
    submission, learner, course, files, history, comments = found
    return AdminSubmissionDetail(
        id=submission.id,
        user_id=learner.id,
        user_email=learner.email,
        user_name=learner.name,
        course_slug=course.slug,
        phase=submission.phase,
        task_no=submission.task_no,
        content=submission.content,
        score=submission.score,
        ai_feedback=submission.ai_feedback,
        submitted_at=submission.submitted_at,
        graded_at=submission.graded_at,
        files=[SubmissionFileOut.from_row(f) for f in files],
        grading_history=[GradingAttemptOut.model_validate(a) for a in history],
        comments=[
            AdminCommentOut(
                id=c.id,
                submission_id=c.submission_id,
                author_user_id=c.author_user_id,
                author_name=author.name,
                body=c.body,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c, author in comments
        ],
    )
