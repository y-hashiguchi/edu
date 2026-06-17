"""Sprint 11 scheduled broadcast cron job tests."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.scheduled_broadcast import (
    ScheduledBroadcast,
    ScheduledBroadcastStatus,
)
from app.services.enrollment import _get_course_by_slug
from app.worker.scheduled_broadcast_job import run_scheduled_broadcast_cron


@pytest.mark.asyncio
async def test_cron_processes_due_row(
    db_session,
    admin_user,
    auth_user,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.worker.scheduled_broadcast_job.settings.scheduled_broadcast_cron_enabled",
        True,
    )
    course = await _get_course_by_slug(db_session, "ai-driven-dev")
    row = ScheduledBroadcast(
        sender_user_id=admin_user.id,
        course_id=course.id,
        title="Cron due",
        body="body",
        link=None,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
        status=ScheduledBroadcastStatus.pending,
    )
    db_session.add(row)
    await db_session.commit()

    await run_scheduled_broadcast_cron({})
    await db_session.refresh(row)
    assert row.status == ScheduledBroadcastStatus.sent
