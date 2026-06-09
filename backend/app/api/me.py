"""`/api/me/...` endpoints — learner-facing actions that read or mutate
the caller's own resources (Sprint 4 onward).

Separated from `/api/submissions/...` and `/api/auth/me` so the BOLA
boundary is structural: every route in this module ends up filtering
the response by `current_user.id`. New `/api/me/...` endpoints should
preserve that invariant.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.comment import CommentCreate, LearnerCommentOut
from app.schemas.notification import NotificationListOut, NotificationOut
from app.services import comment as comment_service
from app.services import notification as notification_service
from app.services.comment import (
    InvalidParentError,
    SubmissionNotFoundError,
    UnauthorizedThreadError,
    post_reply,
)

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get(
    "/submissions/{submission_id}/comments",
    response_model=list[LearnerCommentOut],
)
async def list_my_submission_comments(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LearnerCommentOut]:
    try:
        rows = await comment_service.list_for_owner(
            db, submission_id=submission_id, owner_user_id=user.id
        )
    except comment_service.SubmissionNotFoundError as e:
        # Uniform 404 for both 'submission missing' and 'submission belongs
        # to someone else'. Distinguishing them would leak BOLA signal.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="submission not found"
        ) from e
    return [
        LearnerCommentOut(
            id=c.id,
            author_name=author.name,
            body=c.body,
            created_at=c.created_at,
            parent_id=c.parent_id,
        )
        for c, author in rows
    ]


@router.post(
    "/submissions/{submission_id}/comments",
    response_model=LearnerCommentOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(lambda: settings.me_write_rate_limit)
async def post_my_submission_reply(
    request: Request,
    submission_id: uuid.UUID,
    payload: CommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearnerCommentOut:
    if payload.parent_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="parent_id is required (learners may only reply to existing comments)",
        )
    try:
        reply = await post_reply(
            db=db,
            submission_id=submission_id,
            learner_user_id=user.id,
            parent_id=payload.parent_id,
            body=payload.body,
        )
    except InvalidParentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="parent comment does not belong to this submission",
        ) from e
    except SubmissionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="submission not found",
        ) from e
    except UnauthorizedThreadError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="thread is not anchored to an instructor comment",
        ) from e

    await db.commit()
    return LearnerCommentOut(
        id=reply.id,
        author_name=user.name,
        body=reply.body,
        created_at=reply.created_at,
        parent_id=reply.parent_id,
    )


@router.get("/notifications", response_model=NotificationListOut)
async def list_my_notifications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListOut:
    rows, unread = await notification_service.list_for_recipient(
        db,
        recipient_id=user.id,
        limit=settings.notification_poll_limit,
    )
    return NotificationListOut(
        items=[
            NotificationOut(
                id=n.id,
                recipient_user_id=n.recipient_user_id,
                sender_user_id=n.sender_user_id,
                sender_name=sender.name,
                title=n.title,
                body=n.body,
                link=n.link,
                read_at=n.read_at,
                created_at=n.created_at,
            )
            for n, sender in rows
        ],
        unread_count=unread,
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationOut,
)
@limiter.limit(lambda: settings.me_write_rate_limit)
async def mark_my_notification_read(
    request: Request,  # required by slowapi key_func=get_remote_address
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    try:
        note = await notification_service.mark_read(
            db=db,
            notification_id=notification_id,
            recipient_id=user.id,
        )
    except notification_service.NotificationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="notification not found",
        ) from e
    # Round-trip the sender display name to keep the response shape
    # symmetric with the list endpoint.
    from sqlalchemy import select
    sender = (
        await db.execute(select(User).where(User.id == note.sender_user_id))
    ).scalar_one()
    return NotificationOut(
        id=note.id,
        recipient_user_id=note.recipient_user_id,
        sender_user_id=note.sender_user_id,
        sender_name=sender.name,
        title=note.title,
        body=note.body,
        link=note.link,
        read_at=note.read_at,
        created_at=note.created_at,
    )
