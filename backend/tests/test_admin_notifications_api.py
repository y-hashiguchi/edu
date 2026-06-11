"""Sprint 4 admin-side notifications API tests."""

import uuid as uuid_mod

import pytest

from app.core.security import create_access_token, hash_password


def _auth(client, user_id) -> None:
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


async def _make_learner(db_session, *, email="learner@e.com"):
    from app.models.user import User
    from app.services.progress import initialize_progress

    learner = User(email=email, name="L", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    await db_session.commit()
    await db_session.refresh(learner)
    return learner


@pytest.mark.asyncio
async def test_admin_send_rejects_dangerous_link_scheme(
    client, db_session, admin_user,
):
    """HIGH-1: javascript:/data:/vbscript: schemes cannot reach the DB.

    The DTO validator runs before the service, so the bad scheme is
    rejected with 422 — never written, never echoed back, never
    rendered in any learner's NotificationCenter."""
    learner = await _make_learner(db_session)
    _auth(client, admin_user.id)

    for bad in [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
    ]:
        r = client.post(
            "/api/admin/notifications",
            json={
                "recipient_user_id": str(learner.id),
                "title": "t", "body": "b", "link": bad,
            },
        )
        assert r.status_code == 422, (bad, r.text)


@pytest.mark.asyncio
async def test_admin_send_accepts_safe_schemes(
    client, db_session, admin_user,
):
    """The allowlist must still permit the two real shapes: relative
    SPA paths starting with '/', and http(s) URLs."""
    learner = await _make_learner(db_session)
    _auth(client, admin_user.id)

    for ok in [
        "/phases/2",
        "https://example.com/help",
        "http://internal.local/x",
    ]:
        r = client.post(
            "/api/admin/notifications",
            json={
                "recipient_user_id": str(learner.id),
                "title": "t", "body": "b", "link": ok,
            },
        )
        assert r.status_code == 201, (ok, r.text)


@pytest.mark.asyncio
async def test_admin_send_returns_429_when_inbox_at_unread_cap(
    client, db_session, admin_user, monkeypatch,
):
    """HIGH-2: per-recipient unread cap stops runaway inbox growth.

    Tightens the cap to 3 so we can exercise the boundary without
    sending 200 rows in the test suite."""
    from app.config import settings

    monkeypatch.setattr(settings, "notification_unread_cap", 3)
    learner = await _make_learner(db_session)
    _auth(client, admin_user.id)

    for i in range(3):
        r = client.post(
            "/api/admin/notifications",
            json={
                "recipient_user_id": str(learner.id),
                "title": f"t{i}", "body": "b", "link": None,
            },
        )
        assert r.status_code == 201, r.text

    # The next send is over the cap.
    r = client.post(
        "/api/admin/notifications",
        json={
            "recipient_user_id": str(learner.id),
            "title": "overflow", "body": "b", "link": None,
        },
    )
    assert r.status_code == 429
    assert "inbox full" in r.json()["detail"].lower()
    assert r.headers.get("Retry-After") == "300"


@pytest.mark.asyncio
async def test_unread_cap_resets_after_learner_reads(
    client, db_session, admin_user, monkeypatch,
):
    """Once the learner marks an existing notification read, the admin
    can resume sending — the cap is on UNREAD, not lifetime rows."""
    from app.config import settings
    from app.models.notification import Notification
    from sqlalchemy import select
    from datetime import UTC, datetime

    monkeypatch.setattr(settings, "notification_unread_cap", 2)
    learner = await _make_learner(db_session)
    _auth(client, admin_user.id)

    for i in range(2):
        client.post(
            "/api/admin/notifications",
            json={
                "recipient_user_id": str(learner.id),
                "title": f"t{i}", "body": "b", "link": None,
            },
        )

    # Mark one read directly in the DB so we don't depend on the
    # /api/me/* path in this admin-focused test.
    note = (
        await db_session.execute(
            select(Notification).where(
                Notification.recipient_user_id == learner.id
            ).limit(1)
        )
    ).scalar_one()
    note.read_at = datetime.now(UTC)
    await db_session.commit()

    r = client.post(
        "/api/admin/notifications",
        json={
            "recipient_user_id": str(learner.id),
            "title": "after-read", "body": "b", "link": None,
        },
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_admin_sends_notification(client, db_session, admin_user):
    learner = await _make_learner(db_session)
    _auth(client, admin_user.id)

    r = client.post(
        "/api/admin/notifications",
        json={
            "recipient_user_id": str(learner.id),
            "title": "Phase 1 完了おめでとう",
            "body": "次のフェーズに進めます",
            "link": "/phases/2",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["recipient_user_id"] == str(learner.id)
    assert body["sender_user_id"] == str(admin_user.id)
    assert body["sender_name"] == "講師"
    assert body["title"] == "Phase 1 完了おめでとう"
    assert body["link"] == "/phases/2"
    # A freshly created notification is always unread on insert; the
    # mark-read flow is the only way read_at flips from null.
    assert body["read_at"] is None


@pytest.mark.asyncio
async def test_admin_send_404_when_recipient_missing(client, admin_user):
    """An admin must not be able to seed a row keyed to a non-existent
    user — both because the FK would fail anyway and because returning
    422 from a Pydantic check before reaching the DB gives a clearer
    error to whatever UI triggered it."""
    _auth(client, admin_user.id)
    r = client.post(
        "/api/admin/notifications",
        json={
            "recipient_user_id": str(uuid_mod.uuid4()),
            "title": "x", "body": "x", "link": None,
        },
    )
    assert r.status_code == 404
    assert "recipient" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_send_validates_title_and_body_length(
    client, db_session, admin_user,
):
    learner = await _make_learner(db_session)
    _auth(client, admin_user.id)

    # Empty title
    r = client.post(
        "/api/admin/notifications",
        json={
            "recipient_user_id": str(learner.id),
            "title": "", "body": "x", "link": None,
        },
    )
    assert r.status_code == 422

    # Body too long
    r = client.post(
        "/api/admin/notifications",
        json={
            "recipient_user_id": str(learner.id),
            "title": "x", "body": "y" * 2001, "link": None,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_admin_send_requires_admin(client, db_session):
    """A learner with a valid token cannot send notifications to anyone,
    including themselves."""
    learner = await _make_learner(db_session)
    _auth(client, learner.id)
    r = client.post(
        "/api/admin/notifications",
        json={
            "recipient_user_id": str(learner.id),
            "title": "x", "body": "x", "link": None,
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_send_rate_limited_at_high_rate(
    client, db_session, admin_user, monkeypatch,
):
    """Send burst past admin_write_rate_limit returns 429.

    The limit decorator already has coverage on the comments endpoint;
    this test exists separately because slowapi keys its bucket on the
    *decorated function* — comments and notifications get distinct
    counters by design, so a single shared test would not exercise the
    notifications endpoint's own limit."""
    from app.config import settings
    from app.core.limiter import limiter

    learner = await _make_learner(db_session)
    monkeypatch.setattr(settings, "admin_write_rate_limit", "5/minute")
    monkeypatch.setattr(limiter, "enabled", True)
    try:
        limiter._storage.reset()
    except Exception:  # pragma: no cover
        pass

    _auth(client, admin_user.id)
    statuses = [
        client.post(
            "/api/admin/notifications",
            json={
                "recipient_user_id": str(learner.id),
                "title": f"t{i}", "body": "x", "link": None,
            },
        ).status_code
        for i in range(7)
    ]
    assert 429 in statuses, statuses


@pytest.mark.asyncio
async def test_admin_list_sent_returns_only_own_outbox(
    client, db_session, admin_user,
):
    """An admin's outbox is filtered to notifications they themselves
    sent — co-instructors get their own views."""
    from app.models.notification import Notification
    from app.models.user import User

    learner = await _make_learner(db_session)

    other_admin = User(
        email="other_inst@e.com", name="O",
        password_hash=hash_password("p"), is_admin=True,
    )
    db_session.add(other_admin)
    await db_session.flush()
    db_session.add(Notification(
        recipient_user_id=learner.id,
        sender_user_id=other_admin.id,
        title="x", body="x",
    ))
    db_session.add(Notification(
        recipient_user_id=learner.id,
        sender_user_id=admin_user.id,
        title="mine", body="x",
    ))
    await db_session.commit()

    _auth(client, admin_user.id)
    r = client.get("/api/admin/notifications")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "mine"


@pytest.mark.asyncio
async def test_admin_broadcast_sends_to_course_enrollees(
    client, db_session, admin_user, auth_user,
):
    """LOW-4: course-scoped broadcast reaches active non-admin learners."""
    from app.models.notification import Notification
    from sqlalchemy import func, select

    _auth(client, admin_user.id)
    r = client.post(
        "/api/admin/notifications/broadcast",
        json={
            "course_slug": "ai-driven-dev",
            "title": "全体連絡",
            "body": "今週の課題を確認してください",
            "link": "/courses/ai-driven-dev",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["course_slug"] == "ai-driven-dev"
    assert data["sent_count"] >= 1

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.title == "全体連絡")
        )
    ).scalar_one()
    assert count == data["sent_count"]


@pytest.mark.asyncio
async def test_admin_broadcast_rejects_unknown_course(client, admin_user):
    _auth(client, admin_user.id)
    r = client.post(
        "/api/admin/notifications/broadcast",
        json={
            "course_slug": "no-such-course",
            "title": "t",
            "body": "b",
            "link": None,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_admin_broadcast_skips_admins(
    client, db_session, admin_user, auth_user,
):
    from app.models.notification import Notification
    from sqlalchemy import select

    _auth(client, admin_user.id)
    r = client.post(
        "/api/admin/notifications/broadcast",
        json={
            "course_slug": "ai-driven-dev",
            "title": "admins skipped",
            "body": "body",
            "link": None,
        },
    )
    assert r.status_code == 201
    assert r.json()["skipped_admin"] >= 1

    rows = (
        await db_session.execute(
            select(Notification).where(Notification.title == "admins skipped")
        )
    ).scalars().all()
    recipient_ids = {n.recipient_user_id for n in rows}
    assert admin_user.id not in recipient_ids
