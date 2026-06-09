"""Sprint 6: 受講者が返信を投稿したら、スレッド参加 admin 全員に
Notification 行が自動生成される。"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.instructor_comment import InstructorComment
from app.models.notification import Notification
from app.models.submission import Submission
from app.models.user import User
from app.services.comment import post_reply


async def _make_user(db_session, email, is_admin=False):
    user = User(
        email=email, name=email[:2], password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_submission(db_session, owner):
    sub = Submission(
        user_id=owner.id,
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
async def test_reply_creates_notification_for_single_admin(db_session):
    admin = await _make_user(db_session, "a@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner)
    trunk = InstructorComment(
        submission_id=sub.id, author_user_id=admin.id, body="trunk",
    )
    db_session.add(trunk)
    await db_session.commit()
    await db_session.refresh(trunk)

    await post_reply(
        db=db_session, submission_id=sub.id,
        learner_user_id=learner.id, parent_id=trunk.id,
        body="my reply body",
    )

    notes = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_user_id == admin.id)
        )
    ).scalars().all()
    assert len(notes) == 1
    n = notes[0]
    assert n.sender_user_id == learner.id
    assert n.title == "返信が届きました"
    assert "my reply body" in n.body
    assert n.link == f"/admin/submissions/{sub.id}"


@pytest.mark.asyncio
async def test_reply_creates_notifications_for_multiple_thread_admins(db_session):
    """Two admins participated in the thread → both get notifications."""
    admin_a = await _make_user(db_session, "a@e.com", is_admin=True)
    admin_b = await _make_user(db_session, "b@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner)

    trunk = InstructorComment(
        submission_id=sub.id, author_user_id=admin_a.id, body="A",
    )
    db_session.add(trunk)
    await db_session.flush()
    mid = InstructorComment(
        submission_id=sub.id, author_user_id=admin_b.id,
        body="B follows up", parent_id=trunk.id,
    )
    db_session.add(mid)
    await db_session.commit()
    await db_session.refresh(mid)

    await post_reply(
        db=db_session, submission_id=sub.id,
        learner_user_id=learner.id, parent_id=mid.id,
        body="thanks both",
    )

    rcpts = set(
        (
            await db_session.execute(
                select(Notification.recipient_user_id)
            )
        ).scalars().all()
    )
    assert admin_a.id in rcpts and admin_b.id in rcpts


@pytest.mark.asyncio
async def test_reply_notification_body_truncates_long_text(db_session):
    """UI 表示用に冒頭 120 文字に切り詰める。"""
    admin = await _make_user(db_session, "a@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner)
    trunk = InstructorComment(
        submission_id=sub.id, author_user_id=admin.id, body="trunk",
    )
    db_session.add(trunk)
    await db_session.commit()
    await db_session.refresh(trunk)

    long_body = "あ" * 500
    await post_reply(
        db=db_session, submission_id=sub.id,
        learner_user_id=learner.id, parent_id=trunk.id,
        body=long_body,
    )

    note = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_user_id == admin.id)
        )
    ).scalar_one()
    assert len(note.body) <= 120
