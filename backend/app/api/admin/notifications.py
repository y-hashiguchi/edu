"""Admin → notifications (send, list-sent)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    BroadcastNotificationCreate,
    BroadcastNotificationOut,
    BroadcastScheduleCreate,
    NotificationCreate,
    NotificationOut,
    ScheduledBroadcastCancelOut,
    ScheduledBroadcastListOut,
    ScheduledBroadcastOut,
)
from app.services import notification as notification_service
from app.services import scheduled_broadcast as scheduled_broadcast_service
from app.models.course import Course

router = APIRouter(prefix="/api/admin/notifications", tags=["admin"])


def _scheduled_out(row, course: Course) -> ScheduledBroadcastOut:
    return ScheduledBroadcastOut(
        id=row.id,
        course_slug=course.slug,
        title=row.title,
        body=row.body,
        link=row.link,
        scheduled_at=row.scheduled_at,
        status=row.status,
        sent_at=row.sent_at,
        sent_count=row.sent_count,
        skipped_inbox_full=row.skipped_inbox_full,
        skipped_admin=row.skipped_admin,
        failure_reason=row.failure_reason,
        created_at=row.created_at,
    )


class AdminNotificationListOut(BaseModel):
    items: list[NotificationOut]


@router.post(
    "",
    response_model=NotificationOut,
    status_code=http_status.HTTP_201_CREATED,
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
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="recipient not found",
        ) from e
    except notification_service.RecipientInboxFullError as e:
        # Return 429 instead of 422/409 so the SPA's existing rate-limit
        # handling (ApiCooldownError) can surface a "try again later"
        # message without a new branch. Retry-After hints "minutes" —
        # the cap clears as the learner reads existing items.
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"recipient inbox full (unread cap {e.cap})",
            headers={"Retry-After": "300"},
        ) from e

    return NotificationOut(
        id=note.id,
        recipient_user_id=note.recipient_user_id,
        sender_user_id=note.sender_user_id,
        sender_name=admin.name,
        title=note.title,
        body=note.body,
        link=note.link,
        course_id=note.course_id,
        read_at=note.read_at,
        created_at=note.created_at,
    )


@router.post(
    "/broadcast",
    response_model=BroadcastNotificationOut,
    status_code=http_status.HTTP_201_CREATED,
)
@limiter.limit(lambda: settings.admin_write_rate_limit)
async def broadcast_notification(
    request: Request,
    payload: BroadcastNotificationCreate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> BroadcastNotificationOut:
    try:
        result = await notification_service.broadcast_to_course(
            db=db,
            sender_id=admin.id,
            course_slug=payload.course_slug,
            title=payload.title,
            body=payload.body,
            link=payload.link,
        )
    except notification_service.CourseNotFoundForBroadcastError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown course_slug: {e.slug!r}",
        ) from e

    return BroadcastNotificationOut(
        course_slug=result.course_slug,
        sent_count=result.sent_count,
        skipped_inbox_full=result.skipped_inbox_full,
        skipped_admin=result.skipped_admin,
    )


@router.post(
    "/broadcast/schedule",
    response_model=ScheduledBroadcastOut,
    status_code=http_status.HTTP_201_CREATED,
)
@limiter.limit(lambda: settings.admin_write_rate_limit)
async def schedule_broadcast(
    request: Request,
    payload: BroadcastScheduleCreate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ScheduledBroadcastOut:
    try:
        row = await scheduled_broadcast_service.create_scheduled_broadcast(
            db=db,
            sender_id=admin.id,
            course_slug=payload.course_slug,
            title=payload.title,
            body=payload.body,
            link=payload.link,
            scheduled_at=payload.scheduled_at,
        )
    except notification_service.CourseNotFoundForBroadcastError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown course_slug: {e.slug!r}",
        ) from e
    except scheduled_broadcast_service.InvalidScheduleTimeError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.detail,
        ) from e

    course = (
        await db.execute(select(Course).where(Course.id == row.course_id))
    ).scalar_one()
    return _scheduled_out(row, course)


@router.get("/scheduled", response_model=ScheduledBroadcastListOut)
async def list_scheduled(
    schedule_status: str = Query(default="pending", alias="status"),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ScheduledBroadcastListOut:
    del admin
    allowed = {"pending", "sent", "cancelled", "failed", "all"}
    if schedule_status not in allowed:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of {sorted(allowed)}",
        )
    rows = await scheduled_broadcast_service.list_scheduled_broadcasts(
        db=db,
        status=schedule_status,
    )
    return ScheduledBroadcastListOut(
        items=[_scheduled_out(row, course) for row, course in rows]
    )


@router.delete(
    "/scheduled/{broadcast_id}",
    response_model=ScheduledBroadcastCancelOut,
)
@limiter.limit(lambda: settings.admin_write_rate_limit)
async def cancel_scheduled(
    request: Request,
    broadcast_id: uuid.UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ScheduledBroadcastCancelOut:
    del admin
    try:
        row = await scheduled_broadcast_service.cancel_scheduled_broadcast(
            db=db,
            broadcast_id=broadcast_id,
        )
    except scheduled_broadcast_service.ScheduledBroadcastNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="scheduled broadcast not found",
        ) from e
    except scheduled_broadcast_service.ScheduledBroadcastNotPendingError as e:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="only pending broadcasts can be cancelled",
        ) from e
    return ScheduledBroadcastCancelOut(id=row.id, status=row.status)


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
                course_id=n.course_id,
                read_at=n.read_at,
                created_at=n.created_at,
            )
            for n in rows
        ]
    )
