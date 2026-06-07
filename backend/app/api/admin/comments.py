"""Admin → instructor comments (Sprint 4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import AdminCommentOut
from app.schemas.comment import CommentCreate
from app.services import comment as comment_service

router = APIRouter(prefix="/api/admin/submissions", tags=["admin"])


@router.post(
    "/{submission_id}/comments",
    response_model=AdminCommentOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(lambda: settings.admin_write_rate_limit)
async def post_comment(
    request: Request,  # required by slowapi key_func=get_remote_address
    submission_id: uuid.UUID,
    payload: CommentCreate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCommentOut:
    try:
        comment = await comment_service.create_comment(
            db=db,
            submission_id=submission_id,
            author_user_id=admin.id,
            body=payload.body,
        )
    except comment_service.SubmissionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="submission not found"
        ) from e

    return AdminCommentOut(
        id=comment.id,
        submission_id=comment.submission_id,
        author_user_id=comment.author_user_id,
        author_name=admin.name,
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.get(
    "/{submission_id}/comments",
    response_model=list[AdminCommentOut],
)
async def list_comments(
    submission_id: uuid.UUID,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminCommentOut]:
    rows = await comment_service.list_for_admin(db, submission_id)
    return [
        AdminCommentOut(
            id=c.id,
            submission_id=c.submission_id,
            author_user_id=c.author_user_id,
            author_name=author.name,
            body=c.body,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c, author in rows
    ]
