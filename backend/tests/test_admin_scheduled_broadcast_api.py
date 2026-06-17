"""Sprint 11 admin scheduled broadcast API tests."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token


def _auth(client, user_id) -> None:
    client.headers.update({"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"})


def _future_iso(minutes: int = 10) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


@pytest.mark.asyncio
async def test_schedule_broadcast_201(client, admin_user):
    _auth(client, admin_user.id)
    r = client.post(
        "/api/admin/notifications/broadcast/schedule",
        json={
            "course_slug": "ai-driven-dev",
            "title": "予約連絡",
            "body": "来週から Phase 2",
            "link": "/courses/ai-driven-dev",
            "scheduled_at": _future_iso(15),
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "pending"
    assert data["course_slug"] == "ai-driven-dev"


@pytest.mark.asyncio
async def test_schedule_rejects_past_time(client, admin_user):
    _auth(client, admin_user.id)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    r = client.post(
        "/api/admin/notifications/broadcast/schedule",
        json={
            "course_slug": "ai-driven-dev",
            "title": "t",
            "body": "b",
            "link": None,
            "scheduled_at": past,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_scheduled_pending(client, admin_user):
    _auth(client, admin_user.id)
    client.post(
        "/api/admin/notifications/broadcast/schedule",
        json={
            "course_slug": "ai-driven-dev",
            "title": "List me",
            "body": "b",
            "link": None,
            "scheduled_at": _future_iso(20),
        },
    )
    r = client.get("/api/admin/notifications/scheduled?status=pending")
    assert r.status_code == 200, r.text
    titles = [i["title"] for i in r.json()["items"]]
    assert "List me" in titles


@pytest.mark.asyncio
async def test_cancel_pending(client, admin_user):
    _auth(client, admin_user.id)
    created = client.post(
        "/api/admin/notifications/broadcast/schedule",
        json={
            "course_slug": "ai-driven-dev",
            "title": "Cancel me",
            "body": "b",
            "link": None,
            "scheduled_at": _future_iso(30),
        },
    ).json()
    r = client.delete(f"/api/admin/notifications/scheduled/{created['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_sent_returns_409(client, db_session, admin_user):
    from app.models.scheduled_broadcast import (
        ScheduledBroadcast,
        ScheduledBroadcastStatus,
    )
    from app.services.enrollment import _get_course_by_slug

    course = await _get_course_by_slug(db_session, "ai-driven-dev")
    row = ScheduledBroadcast(
        sender_user_id=admin_user.id,
        course_id=course.id,
        title="Done",
        body="b",
        link=None,
        scheduled_at=datetime.now(UTC),
        status=ScheduledBroadcastStatus.sent,
        sent_at=datetime.now(UTC),
        sent_count=0,
    )
    db_session.add(row)
    await db_session.commit()

    _auth(client, admin_user.id)
    r = client.delete(f"/api/admin/notifications/scheduled/{row.id}")
    assert r.status_code == 409
