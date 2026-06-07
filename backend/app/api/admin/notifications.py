"""Admin → notifications (send, list-sent)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationCreate,
    NotificationOut,
)
from app.services import notification as notification_service

router = APIRouter(prefix="/api/admin/notifications", tags=["admin"])


class AdminNotificationListOut(BaseModel):
    items: list[NotificationOut]


@router.post(
    "",
    response_model=NotificationOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(lambda: settings.admin_write_rate_limit)
async def send_notification(
    request: Request,  # required by slowapi key_func=get_remote_address
    payload: NotificationCreate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    try:
        note = await notification_service.send(
            db=db,
            sender_id=admin.id,
            recipient_id=payload.recipient_user_id,
            title=payload.title,
            body=payload.body,
            link=payload.link,
        )
    except notification_service.RecipientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="recipient not found",
        ) from e

    return NotificationOut(
        id=note.id,
        recipient_user_id=note.recipient_user_id,
        sender_user_id=note.sender_user_id,
        sender_name=admin.name,
        title=note.title,
        body=note.body,
        link=note.link,
        read_at=note.read_at,
        created_at=note.created_at,
    )


@router.get("", response_model=AdminNotificationListOut)
async def list_sent(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminNotificationListOut:
    rows = await notification_service.list_sent_by(db, admin.id)
    if not rows:
        return AdminNotificationListOut(items=[])

    # Resolve recipient names for display in the outbox. The outbox is
    # the admin's own list — typically O(10s) rows — so a single bulk
    # lookup over distinct recipients is cheaper than a join per row.
    recipient_ids = {r.recipient_user_id for r in rows}
    recipients = {
        u.id: u
        for u in (
            await db.execute(select(User).where(User.id.in_(recipient_ids)))
        ).scalars().all()
    }
    return AdminNotificationListOut(
        items=[
            NotificationOut(
                id=n.id,
                recipient_user_id=n.recipient_user_id,
                sender_user_id=n.sender_user_id,
                sender_name=admin.name,
                title=n.title,
                body=n.body,
                link=n.link,
                read_at=n.read_at,
                created_at=n.created_at,
            )
            for n in rows
        ]
    )
