"""Sprint 11 scheduled broadcast service tests."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.scheduled_broadcast import (
    ScheduledBroadcast,
    ScheduledBroadcastStatus,
)
from app.services.enrollment import _get_course_by_slug
from app.services.scheduled_broadcast import (
    InvalidScheduleTimeError,
    ScheduledBroadcastNotPendingError,
    cancel_scheduled_broadcast,
    create_scheduled_broadcast,
    process_due_scheduled_broadcasts,
)


def _future(minutes: int = 10) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


@pytest.mark.asyncio
async def test_create_scheduled_broadcast_pending(db_session, admin_user):
    row = await create_scheduled_broadcast(
        db=db_session,
        sender_id=admin_user.id,
        course_slug="ai-driven-dev",
        title="Reminder",
        body="Phase 2 starts Monday",
        link="/courses/ai-driven-dev",
        scheduled_at=_future(10),
    )
    assert row.status == ScheduledBroadcastStatus.pending
    assert row.sent_at is None


@pytest.mark.asyncio
async def test_create_rejects_past_schedule(db_session, admin_user):
    with pytest.raises(InvalidScheduleTimeError):
        await create_scheduled_broadcast(
            db=db_session,
            sender_id=admin_user.id,
            course_slug="ai-driven-dev",
            title="Late",
            body="b",
            link=None,
            scheduled_at=datetime.now(UTC) - timedelta(hours=1),
        )


@pytest.mark.asyncio
async def test_cancel_pending(db_session, admin_user):
    row = await create_scheduled_broadcast(
        db=db_session,
        sender_id=admin_user.id,
        course_slug="ai-driven-dev",
        title="x",
        body="y",
        link=None,
        scheduled_at=_future(20),
    )
    cancelled = await cancel_scheduled_broadcast(db=db_session, broadcast_id=row.id)
    assert cancelled.status == ScheduledBroadcastStatus.cancelled


@pytest.mark.asyncio
async def test_cancel_sent_raises(db_session, admin_user):
    row = await create_scheduled_broadcast(
        db=db_session,
        sender_id=admin_user.id,
        course_slug="ai-driven-dev",
        title="x",
        body="y",
        link=None,
        scheduled_at=_future(20),
    )
    row.status = ScheduledBroadcastStatus.sent
    await db_session.commit()
    with pytest.raises(ScheduledBroadcastNotPendingError):
        await cancel_scheduled_broadcast(db=db_session, broadcast_id=row.id)


@pytest.mark.asyncio
async def test_process_due_marks_sent(
    db_session,
    admin_user,
    auth_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.scheduled_broadcast.settings.scheduled_broadcast_cron_enabled",
        True,
    )
    course = await _get_course_by_slug(db_session, "ai-driven-dev")
    row = ScheduledBroadcast(
        sender_user_id=admin_user.id,
        course_id=course.id,
        title="Due now",
        body="Hello cohort",
        link=None,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
        status=ScheduledBroadcastStatus.pending,
    )
    db_session.add(row)
    await db_session.commit()

    count = await process_due_scheduled_broadcasts(db_session)
    assert count == 1
    await db_session.refresh(row)
    assert row.status == ScheduledBroadcastStatus.sent
    assert row.sent_count is not None
    assert row.sent_count >= 1


@pytest.mark.asyncio
async def test_process_due_idempotent_on_sent(db_session, admin_user, monkeypatch):
    monkeypatch.setattr(
        "app.services.scheduled_broadcast.settings.scheduled_broadcast_cron_enabled",
        True,
    )
    course = await _get_course_by_slug(db_session, "ai-driven-dev")
    row = ScheduledBroadcast(
        sender_user_id=admin_user.id,
        course_id=course.id,
        title="Already sent",
        body="b",
        link=None,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
        status=ScheduledBroadcastStatus.sent,
        sent_at=datetime.now(UTC),
        sent_count=0,
    )
    db_session.add(row)
    await db_session.commit()

    count = await process_due_scheduled_broadcasts(db_session)
    assert count == 0
