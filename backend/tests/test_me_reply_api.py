"""Sprint 6: POST /api/me/submissions/{id}/comments — 受講者返信投稿 API."""

from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token, hash_password
from app.models.instructor_comment import InstructorComment
from app.models.submission import Submission
from app.models.user import User


def _auth(client, user_id):
    client.headers.update({"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"})


async def _make_user(db_session, email, is_admin=False):
    user = User(
        email=email,
        name=email[:2],
        password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_submission(db_session, owner, course_id):
    sub = Submission(
        user_id=owner.id,
        course_id=course_id,
        phase=1,
        task_no=1,
        content="x",
        submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


@pytest.mark.asyncio
async def test_post_reply_happy_path(client, db_session, default_course_id):
    admin = await _make_user(db_session, "a@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner, default_course_id)
    trunk = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin.id,
        body="trunk",
    )
    db_session.add(trunk)
    await db_session.commit()
    await db_session.refresh(trunk)

    _auth(client, learner.id)
    r = client.post(
        f"/api/me/submissions/{sub.id}/comments",
        json={"parent_id": str(trunk.id), "body": "thanks!"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["parent_id"] == str(trunk.id)
    assert body["body"] == "thanks!"
    assert body["author_name"] == learner.name


@pytest.mark.asyncio
async def test_post_reply_requires_parent_id_field(client, db_session, default_course_id):
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner, default_course_id)
    _auth(client, learner.id)

    r = client.post(
        f"/api/me/submissions/{sub.id}/comments",
        json={"body": "no parent"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_reply_returns_400_for_parent_in_different_submission(
    client,
    db_session,
    default_course_id,
):
    admin = await _make_user(db_session, "a@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub_a = await _make_submission(db_session, learner, default_course_id)
    sub_b = Submission(
        user_id=learner.id,
        course_id=default_course_id,
        phase=1,
        task_no=2,
        content="x",
        submitted_at=datetime.now(UTC),
    )
    db_session.add(sub_b)
    await db_session.commit()
    await db_session.refresh(sub_b)
    trunk_b = InstructorComment(
        submission_id=sub_b.id,
        author_user_id=admin.id,
        body="trunk in B",
    )
    db_session.add(trunk_b)
    await db_session.commit()
    await db_session.refresh(trunk_b)

    _auth(client, learner.id)
    r = client.post(
        f"/api/me/submissions/{sub_a.id}/comments",
        json={"parent_id": str(trunk_b.id), "body": "oops"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_post_reply_returns_404_for_other_users_submission(
    client,
    db_session,
    default_course_id,
):
    admin = await _make_user(db_session, "a@e.com", is_admin=True)
    owner = await _make_user(db_session, "o@e.com")
    intruder = await _make_user(db_session, "i@e.com")
    sub = await _make_submission(db_session, owner, default_course_id)
    trunk = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin.id,
        body="trunk",
    )
    db_session.add(trunk)
    await db_session.commit()
    await db_session.refresh(trunk)

    _auth(client, intruder.id)
    r = client.post(
        f"/api/me/submissions/{sub.id}/comments",
        json={"parent_id": str(trunk.id), "body": "evil"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_reply_rate_limited(client, db_session, monkeypatch, default_course_id):
    """`me_write_rate_limit` を 5/minute に絞って 7 回連投 → 429 が混じる。"""
    from app.api.me import settings as me_settings
    from app.core.limiter import limiter

    admin = await _make_user(db_session, "a@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner, default_course_id)
    trunk = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin.id,
        body="trunk",
    )
    db_session.add(trunk)
    await db_session.commit()
    await db_session.refresh(trunk)

    monkeypatch.setattr(me_settings, "me_write_rate_limit", "5/minute")
    monkeypatch.setattr(limiter, "enabled", True)
    try:
        limiter._storage.reset()
    except Exception:  # pragma: no cover
        pass

    _auth(client, learner.id)
    statuses = [
        client.post(
            f"/api/me/submissions/{sub.id}/comments",
            json={"parent_id": str(trunk.id), "body": f"r{i}"},
        ).status_code
        for i in range(7)
    ]
    assert 429 in statuses, statuses
