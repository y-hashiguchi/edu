"""Sprint 4 admin submissions API tests."""

import uuid as uuid_mod
from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token, hash_password


def _auth(client, user_id) -> None:
    client.headers.update({"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"})


async def _seed_learner_with_submissions(db_session, course_id, *, email="learner@e.com"):
    from app.models.submission import Submission
    from app.models.user import User
    from app.services.progress import initialize_progress

    learner = User(email=email, name="L", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)

    s1 = Submission(
        user_id=learner.id,
        course_id=course_id,
        phase=1,
        task_no=1,
        content="phase 1 essay",
        score=72,
        submitted_at=datetime.now(UTC),
    )
    s2 = Submission(
        user_id=learner.id,
        course_id=course_id,
        phase=2,
        task_no=1,
        content="phase 2 essay",
        score=88,
        submitted_at=datetime.now(UTC),
    )
    db_session.add_all([s1, s2])
    await db_session.commit()
    await db_session.refresh(s1)
    await db_session.refresh(s2)
    return learner, s1, s2


@pytest.mark.asyncio
async def test_list_submissions_requires_admin(client, db_session):
    """Logged-in learners cannot see the cross-cohort submissions feed."""
    from app.models.user import User
    from app.services.progress import initialize_progress

    learner = User(email="x@e.com", name="x", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    await db_session.commit()

    _auth(client, learner.id)
    r = client.get("/api/admin/submissions")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_submissions_unauthenticated_returns_401(client):
    r = client.get("/api/admin/submissions")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_submissions_filters_by_user_and_phase(
    client,
    db_session,
    admin_user,
    default_course_id,
):
    learner, _s1, _s2 = await _seed_learner_with_submissions(db_session, default_course_id)
    _auth(client, admin_user.id)

    # No filter — both submissions returned
    r = client.get("/api/admin/submissions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2

    # Filter by user
    r = client.get(f"/api/admin/submissions?user_id={learner.id}")
    body = r.json()
    assert body["total"] == 2
    assert {item["phase"] for item in body["items"]} == {1, 2}

    # Filter by phase
    r = client.get(f"/api/admin/submissions?user_id={learner.id}&phase=1")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["phase"] == 1


@pytest.mark.asyncio
async def test_list_submissions_carries_user_columns(
    client,
    db_session,
    admin_user,
    default_course_id,
):
    """Each summary row must let the dashboard show 'who' without an
    extra round-trip per user (one of the dashboard's hot paths)."""
    learner, *_ = await _seed_learner_with_submissions(db_session, default_course_id)
    _auth(client, admin_user.id)

    r = client.get(f"/api/admin/submissions?user_id={learner.id}&phase=1")
    item = r.json()["items"][0]
    assert item["user_id"] == str(learner.id)
    assert item["user_email"] == "learner@e.com"
    assert item["user_name"] == "L"
    assert item["score"] == 72


@pytest.mark.asyncio
async def test_list_submissions_pagination(client, db_session, admin_user, default_course_id):
    from app.models.submission import Submission
    from app.models.user import User
    from app.services.progress import initialize_progress

    learner = User(email="m@e.com", name="m", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    for task in range(1, 5):
        db_session.add(
            Submission(
                user_id=learner.id,
                course_id=default_course_id,
                phase=1,
                task_no=task,
                content=f"t{task}",
                submitted_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    _auth(client, admin_user.id)
    p1 = client.get(f"/api/admin/submissions?user_id={learner.id}&limit=2&offset=0").json()
    p2 = client.get(f"/api/admin/submissions?user_id={learner.id}&limit=2&offset=2").json()
    assert len(p1["items"]) == 2
    assert len(p2["items"]) == 2
    assert p1["total"] == p2["total"] == 4
    assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})


@pytest.mark.asyncio
async def test_list_submissions_caps_limit(client, admin_user):
    _auth(client, admin_user.id)
    assert client.get("/api/admin/submissions?limit=999").status_code == 422


@pytest.mark.asyncio
async def test_submission_detail_includes_files_history_and_comments(
    client,
    db_session,
    admin_user,
    default_course_id,
):
    """Detail view bundles everything the dashboard needs in one
    response — admin should never have to make a second call to
    discover, e.g., whether comments already exist."""
    learner, s1, _ = await _seed_learner_with_submissions(db_session, default_course_id)
    _auth(client, admin_user.id)

    r = client.get(f"/api/admin/submissions/{s1.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(s1.id)
    assert body["user_email"] == "learner@e.com"
    assert body["content"] == "phase 1 essay"
    assert body["score"] == 72
    # Empty arrays — not missing keys — so the frontend can `length`-check.
    assert body["files"] == []
    assert body["grading_history"] == []
    assert body["comments"] == []


@pytest.mark.asyncio
async def test_submission_detail_404_for_unknown_id(client, admin_user):
    _auth(client, admin_user.id)
    r = client.get(f"/api/admin/submissions/{uuid_mod.uuid4()}")
    assert r.status_code == 404
