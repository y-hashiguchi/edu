"""Sprint 4 admin users API tests."""

import pytest

from app.core.security import create_access_token, hash_password


async def _make_learners(db, n: int):
    from app.models.user import User
    from app.services.progress import initialize_progress

    users = []
    for i in range(n):
        u = User(
            email=f"l{i}@example.com",
            name=f"L{i}",
            password_hash=hash_password("p"),
        )
        db.add(u)
        await db.flush()
        await initialize_progress(db, u.id)
        users.append(u)
    await db.commit()
    return users


def _auth(client, user_id) -> None:
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


@pytest.mark.asyncio
async def test_list_users_rejects_non_admin(client, db_session):
    """Without `is_admin=True`, a logged-in learner gets a 403, not data."""
    learner = (await _make_learners(db_session, 1))[0]
    _auth(client, learner.id)
    r = client.get("/api/admin/users")
    assert r.status_code == 403
    assert "admin" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_users_unauthenticated_returns_401(client):
    """No token → 401 (auth layer), not 403 (RBAC layer)."""
    r = client.get("/api/admin/users")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_users_returns_admin_plus_learners(
    client, db_session, admin_user
):
    await _make_learners(db_session, 3)
    _auth(client, admin_user.id)

    r = client.get("/api/admin/users")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    # 3 learners + 1 admin
    assert body["total"] == 4
    assert len(body["items"]) == 4

    emails = {item["email"] for item in body["items"]}
    assert "instructor@example.com" in emails
    assert {"l0@example.com", "l1@example.com", "l2@example.com"} <= emails

    # Each summary row carries the progress aggregate used by the dashboard
    sample = body["items"][0]
    assert "completed_phases" in sample
    assert "in_progress_phases" in sample
    assert "is_admin" in sample


@pytest.mark.asyncio
async def test_list_users_aggregate_counts_match_phase_states(
    client, db_session, admin_user
):
    """Progress counts: a learner with 1 phase completed and 1 in
    progress should report exactly those numbers — not the raw row count
    of their progress rows (4 phases x 1 row each = 4)."""
    from sqlalchemy import select

    from app.models.progress import Progress, ProgressStatus

    learner = (await _make_learners(db_session, 1))[0]

    rows = (
        await db_session.execute(
            select(Progress).where(Progress.user_id == learner.id)
            .order_by(Progress.phase)
        )
    ).scalars().all()
    rows[0].status = ProgressStatus.COMPLETED.value
    rows[1].status = ProgressStatus.IN_PROGRESS.value
    await db_session.commit()

    _auth(client, admin_user.id)
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    items = {item["email"]: item for item in r.json()["items"]}
    summary = items["l0@example.com"]
    assert summary["completed_phases"] == 1
    assert summary["in_progress_phases"] == 1


@pytest.mark.asyncio
async def test_list_users_pagination(client, db_session, admin_user):
    await _make_learners(db_session, 5)
    _auth(client, admin_user.id)

    page1 = client.get("/api/admin/users?limit=2&offset=0").json()
    page2 = client.get("/api/admin/users?limit=2&offset=2").json()
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    # No overlap between pages
    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    assert ids1.isdisjoint(ids2)
    assert page1["total"] == page2["total"] == 6  # 5 learners + 1 admin


@pytest.mark.asyncio
async def test_list_users_caps_limit(client, db_session, admin_user):
    """Unbounded `limit` is a DOS vector; the server caps it."""
    _auth(client, admin_user.id)
    r = client.get("/api/admin/users?limit=99999")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_user_detail_returns_four_phase_progress_and_latest_scores(
    client, db_session, admin_user, default_course_id
):
    from datetime import UTC, datetime

    from app.models.submission import Submission

    learner = (await _make_learners(db_session, 1))[0]
    # Two attempts on phase 1, task 1 — admin view shows the latest score
    # (which is the cached value on the submission row).
    db_session.add(
        Submission(
            user_id=learner.id, course_id=default_course_id, phase=1, task_no=1, content="v",
            score=72, submitted_at=datetime.now(UTC),
        )
    )
    db_session.add(
        Submission(
            user_id=learner.id, course_id=default_course_id, phase=2, task_no=1, content="v",
            score=88, submitted_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    _auth(client, admin_user.id)
    r = client.get(f"/api/admin/users/{learner.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(learner.id)
    assert body["email"] == "l0@example.com"
    assert len(body["progress"]) == 4
    assert {p["phase"] for p in body["progress"]} == {1, 2, 3, 4}
    # latest_scores is keyed by phase number; phases without graded
    # submissions appear as null.
    scores = body["latest_scores"]
    assert scores["1"] == 72
    assert scores["2"] == 88
    assert scores["3"] is None
    assert scores["4"] is None


@pytest.mark.asyncio
async def test_user_detail_404_for_unknown_user(client, admin_user):
    import uuid as uuid_mod

    _auth(client, admin_user.id)
    r = client.get(f"/api/admin/users/{uuid_mod.uuid4()}")
    assert r.status_code == 404
