"""Sprint 4 learner-side notifications API tests.

Pairs with test_admin_notifications_api.py — the admin tests cover the
send path, this file covers the read + mark-read path with BOLA fences.
"""

import uuid as uuid_mod
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token, hash_password


def _auth(client, user_id) -> None:
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


async def _make_learner(db_session, *, email="l@e.com"):
    from app.models.user import User
    from app.services.progress import initialize_progress

    learner = User(email=email, name="L", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    await db_session.commit()
    await db_session.refresh(learner)
    return learner


async def _seed_notification(db_session, sender, recipient, *, title="hi", body="x"):
    from app.models.notification import Notification

    note = Notification(
        recipient_user_id=recipient.id,
        sender_user_id=sender.id,
        title=title,
        body=body,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    return note


@pytest.mark.asyncio
async def test_list_returns_only_own_inbox_newest_first(
    client, db_session, admin_user,
):
    """Two learners + two notifications each; only the requesting
    learner's inbox is returned, sorted newest first."""
    a = await _make_learner(db_session, email="a@e.com")
    b = await _make_learner(db_session, email="b@e.com")

    older = await _seed_notification(db_session, admin_user, a, title="first")
    # Force temporal ordering so the sort assertion is meaningful even
    # when the clock granularity collapses to the millisecond.
    older.created_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    await _seed_notification(db_session, admin_user, a, title="second")
    await _seed_notification(db_session, admin_user, b, title="for-b")

    _auth(client, a.id)
    r = client.get("/api/me/notifications")
    assert r.status_code == 200
    body = r.json()
    titles = [n["title"] for n in body["items"]]
    assert titles == ["second", "first"]
    assert body["unread_count"] == 2


@pytest.mark.asyncio
async def test_unread_count_excludes_read_rows(
    client, db_session, admin_user,
):
    learner = await _make_learner(db_session)
    n1 = await _seed_notification(db_session, admin_user, learner)
    await _seed_notification(db_session, admin_user, learner)
    n1.read_at = datetime.now(UTC)
    await db_session.commit()

    _auth(client, learner.id)
    body = client.get("/api/me/notifications").json()
    assert body["unread_count"] == 1
    assert len(body["items"]) == 2  # list shows both, just count differs


@pytest.mark.asyncio
async def test_mark_read_sets_read_at_and_is_idempotent(
    client, db_session, admin_user,
):
    learner = await _make_learner(db_session)
    note = await _seed_notification(db_session, admin_user, learner)

    _auth(client, learner.id)
    r = client.post(f"/api/me/notifications/{note.id}/read")
    assert r.status_code == 200, r.text
    assert client.get("/api/me/notifications").json()["unread_count"] == 0

    # Idempotent: running again is still 200, no state change.
    r2 = client.post(f"/api/me/notifications/{note.id}/read")
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_intruder_cannot_mark_others_notification_read(
    client, db_session, admin_user,
):
    """BOLA: a learner with a valid token cannot mark someone else's
    notification read by guessing the ID. Returns 404 (never 403) so
    ownership is not leakable from the response code."""
    owner = await _make_learner(db_session, email="own@e.com")
    intruder = await _make_learner(db_session, email="int@e.com")
    note = await _seed_notification(db_session, admin_user, owner)

    _auth(client, intruder.id)
    r = client.post(f"/api/me/notifications/{note.id}/read")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mark_read_404_for_unknown_id(client, db_session):
    learner = await _make_learner(db_session)
    _auth(client, learner.id)
    r = client.post(f"/api/me/notifications/{uuid_mod.uuid4()}/read")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_caps_at_notification_poll_limit(
    client, db_session, admin_user,
):
    """Default cap from settings.notification_poll_limit keeps the
    30-second poll cheap regardless of inbox depth."""
    from app.config import settings

    learner = await _make_learner(db_session)
    # Seed one above the configured cap.
    for i in range(settings.notification_poll_limit + 5):
        await _seed_notification(db_session, admin_user, learner, title=f"t{i}")

    _auth(client, learner.id)
    body = client.get("/api/me/notifications").json()
    assert len(body["items"]) == settings.notification_poll_limit
    # The count, however, is the true total of unread — clients use this
    # to render the badge, and an undercount would mask real backlog.
    assert body["unread_count"] == settings.notification_poll_limit + 5


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client):
    assert client.get("/api/me/notifications").status_code == 401
    assert client.post(
        f"/api/me/notifications/{uuid_mod.uuid4()}/read"
    ).status_code == 401
