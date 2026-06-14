"""Scheduled broadcast domain service (Sprint 11)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.courses import COURSE_REGISTRY
from app.models.course import Course
from app.models.scheduled_broadcast import (
    ScheduledBroadcast,
    ScheduledBroadcastStatus,
)
from app.services.enrollment import _get_course_by_slug
from app.services.notification import (
    CourseNotFoundForBroadcastError,
    broadcast_to_course,
)


class ScheduledBroadcastNotFoundError(Exception):
    pass


class ScheduledBroadcastNotPendingError(Exception):
    pass


class InvalidScheduleTimeError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _validate_scheduled_at(scheduled_at: datetime) -> None:
    if scheduled_at.tzinfo is None:
        raise InvalidScheduleTimeError("scheduled_at must be timezone-aware")
    now = datetime.now(UTC)
    scheduled_utc = scheduled_at.astimezone(UTC)
    min_at = now + timedelta(minutes=settings.scheduled_broadcast_min_lead_minutes)
    max_at = now + timedelta(days=settings.scheduled_broadcast_max_horizon_days)
    if scheduled_utc <= min_at:
        raise InvalidScheduleTimeError(
            f"scheduled_at must be at least "
            f"{settings.scheduled_broadcast_min_lead_minutes} minutes in the future"
        )
    if scheduled_utc > max_at:
        raise InvalidScheduleTimeError(
            f"scheduled_at must be within "
            f"{settings.scheduled_broadcast_max_horizon_days} days"
        )


async def create_scheduled_broadcast(
    *,
    db: AsyncSession,
    sender_id: uuid.UUID,
    course_slug: str,
    title: str,
    body: str,
    link: str | None,
    scheduled_at: datetime,
) -> ScheduledBroadcast:
    if course_slug not in COURSE_REGISTRY:
        raise CourseNotFoundForBroadcastError(course_slug)
    _validate_scheduled_at(scheduled_at)
    course = await _get_course_by_slug(db, course_slug)
    row = ScheduledBroadcast(
        sender_user_id=sender_id,
        course_id=course.id,
        title=title,
        body=body,
        link=link,
        scheduled_at=scheduled_at.astimezone(UTC),
        status=ScheduledBroadcastStatus.pending,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def cancel_scheduled_broadcast(
    *,
    db: AsyncSession,
    broadcast_id: uuid.UUID,
) -> ScheduledBroadcast:
    row = (
        await db.execute(
            select(ScheduledBroadcast).where(ScheduledBroadcast.id == broadcast_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ScheduledBroadcastNotFoundError(str(broadcast_id))
    if row.status != ScheduledBroadcastStatus.pending:
        raise ScheduledBroadcastNotPendingError(str(broadcast_id))
    row.status = ScheduledBroadcastStatus.cancelled
    await db.commit()
    await db.refresh(row)
    return row


async def list_scheduled_broadcasts(
    *,
    db: AsyncSession,
    status: str | None = None,
    limit: int = 50,
) -> list[tuple[ScheduledBroadcast, Course]]:
    stmt = (
        select(ScheduledBroadcast, Course)
        .join(Course, Course.id == ScheduledBroadcast.course_id)
        .order_by(ScheduledBroadcast.scheduled_at.desc())
        .limit(limit)
    )
    if status and status != "all":
        stmt = stmt.where(ScheduledBroadcast.status == status)
    return list((await db.execute(stmt)).all())


async def process_due_scheduled_broadcasts(db: AsyncSession) -> int:
    """Process pending rows whose scheduled_at has passed. Returns count processed."""
    if not settings.scheduled_broadcast_cron_enabled:
        return 0

    now = datetime.now(UTC)
    due_rows = list(
        (
            await db.execute(
                select(ScheduledBroadcast)
                .where(
                    ScheduledBroadcast.status == ScheduledBroadcastStatus.pending,
                    ScheduledBroadcast.scheduled_at <= now,
                )
                .with_for_update(skip_locked=True)
                .order_by(ScheduledBroadcast.scheduled_at)
                .limit(settings.scheduled_broadcast_batch_size)
            )
        ).scalars().all()
    )

    processed = 0
    for row in due_rows:
        if row.status != ScheduledBroadcastStatus.pending:
            continue
        course = (
            await db.execute(select(Course).where(Course.id == row.course_id))
        ).scalar_one()
        try:
            result = await broadcast_to_course(
                db=db,
                sender_id=row.sender_user_id,
                course_slug=course.slug,
                title=row.title,
                body=row.body,
                link=row.link,
            )
            row.status = ScheduledBroadcastStatus.sent
            row.sent_at = datetime.now(UTC)
            row.sent_count = result.sent_count
            row.skipped_inbox_full = result.skipped_inbox_full
            row.skipped_admin = result.skipped_admin
            row.failure_reason = None
        except Exception as exc:  # noqa: BLE001 — record failure, continue batch
            row.status = ScheduledBroadcastStatus.failed
            row.failure_reason = str(exc)[:2000]
        await db.commit()
        await db.refresh(row)
        processed += 1
    return processed
