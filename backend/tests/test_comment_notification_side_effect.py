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
async def test_reply_creates_notification_for_single_admin(db_session, default_course_id):
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

    await post_reply(
        db=db_session,
        submission_id=sub.id,
        learner_user_id=learner.id,
        parent_id=trunk.id,
        body="my reply body",
    )

    notes = (
        (
            await db_session.execute(
                select(Notification).where(Notification.recipient_user_id == admin.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(notes) == 1
    n = notes[0]
    assert n.sender_user_id == learner.id
    assert n.title == "返信が届きました"
    assert "my reply body" in n.body
    assert n.link == f"/admin/submissions/{sub.id}"


@pytest.mark.asyncio
async def test_reply_creates_notifications_for_multiple_thread_admins(
    db_session, default_course_id
):
    """Two admins participated in the thread → both get notifications."""
    admin_a = await _make_user(db_session, "a@e.com", is_admin=True)
    admin_b = await _make_user(db_session, "b@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner, default_course_id)

    trunk = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin_a.id,
        body="A",
    )
    db_session.add(trunk)
    await db_session.flush()
    mid = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin_b.id,
        body="B follows up",
        parent_id=trunk.id,
    )
    db_session.add(mid)
    await db_session.commit()
    await db_session.refresh(mid)

    await post_reply(
        db=db_session,
        submission_id=sub.id,
        learner_user_id=learner.id,
        parent_id=mid.id,
        body="thanks both",
    )

    rcpts = set((await db_session.execute(select(Notification.recipient_user_id))).scalars().all())
    assert admin_a.id in rcpts and admin_b.id in rcpts


@pytest.mark.asyncio
async def test_reply_notification_body_truncates_long_text(db_session, default_course_id):
    """UI 表示用に冒頭 120 文字に切り詰める。"""
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

    long_body = "あ" * 500
    await post_reply(
        db=db_session,
        submission_id=sub.id,
        learner_user_id=learner.id,
        parent_id=trunk.id,
        body=long_body,
    )

    note = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_user_id == admin.id)
        )
    ).scalar_one()
    assert len(note.body) <= 120


@pytest.mark.asyncio
async def test_reply_notifies_sibling_branch_admin(db_session, default_course_id):
    """HIGH-3 (sprint-6 follow-up): admin B が trunk へ直接返信 (sibling branch)
    した状態で、学習者が trunk へ返信したとき、admin B にも通知が届くこと。

    Before fix: ancestor-only traversal only walked up from the learner's
    chosen parent (trunk). admin B's reply is a sibling — not on that
    ancestor path — so admin B was silently missed.

    After fix: traversal walks the entire thread tree from root, so any
    admin who participated anywhere in the thread is notified."""
    admin_a = await _make_user(db_session, "a@e.com", is_admin=True)
    admin_b = await _make_user(db_session, "b@e.com", is_admin=True)
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner, default_course_id)

    # admin A's trunk
    trunk = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin_a.id,
        body="A trunk",
    )
    db_session.add(trunk)
    await db_session.flush()
    # admin B replies directly to trunk (sibling to whatever learner posts)
    sibling = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin_b.id,
        body="B sibling",
        parent_id=trunk.id,
    )
    db_session.add(sibling)
    await db_session.commit()
    await db_session.refresh(trunk)

    # Learner replies to trunk (NOT to sibling). Old traversal would miss B.
    await post_reply(
        db=db_session,
        submission_id=sub.id,
        learner_user_id=learner.id,
        parent_id=trunk.id,
        body="learner reply to trunk",
    )

    rcpts = set((await db_session.execute(select(Notification.recipient_user_id))).scalars().all())
    assert admin_a.id in rcpts, "admin A (trunk author) should be notified"
    assert admin_b.id in rcpts, "admin B (sibling branch) should also be notified"
