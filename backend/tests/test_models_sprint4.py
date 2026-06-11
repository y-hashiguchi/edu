"""Sprint 4 model tests: is_admin, instructor_comments, notifications."""

from datetime import UTC, datetime

import pytest

from app.core.security import hash_password
from app.models.submission import Submission
from app.models.user import User


@pytest.mark.asyncio
async def test_user_is_admin_default_false(db_session):
    """A freshly inserted user is NOT an admin unless the row says so.

    This is the load-bearing default for the whole RBAC story: the
    `get_current_admin` dependency, the alembic migration's
    server_default, and every existing pre-Sprint-4 user all rely on
    `is_admin` reading False by default.
    """
    user = User(
        email="reg@example.com",
        name="r",
        password_hash=hash_password("p"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_admin is False


@pytest.mark.asyncio
async def test_user_is_admin_can_be_true(db_session):
    """Explicitly opting a user in to admin status round-trips through
    the DB as True (not 1, not 't', not 'true' string)."""
    user = User(
        email="adm@example.com",
        name="a",
        password_hash=hash_password("p"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_admin is True


async def _make_admin_and_learner(db_session) -> tuple[User, User]:
    admin = User(
        email="instructor@example.com", name="講師",
        password_hash=hash_password("p"), is_admin=True,
    )
    learner = User(
        email="learner@example.com", name="受講者",
        password_hash=hash_password("p"),
    )
    db_session.add_all([admin, learner])
    await db_session.flush()
    return admin, learner


@pytest.mark.asyncio
async def test_instructor_comment_round_trips(db_session, default_course_id):
    from app.models.instructor_comment import InstructorComment

    admin, learner = await _make_admin_and_learner(db_session)
    sub = Submission(
        user_id=learner.id, course_id=default_course_id, phase=1, task_no=1,
        content="x", submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.flush()

    comment = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin.id,
        body="phase 2 をもう少し具体的に書くと良いです。",
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)

    assert comment.id is not None
    assert comment.body.startswith("phase 2")
    assert comment.created_at is not None
    assert comment.updated_at is not None


@pytest.mark.asyncio
async def test_instructor_comment_cascades_on_submission_delete(
    db_session, default_course_id
):
    """Deleting a submission must remove its comments (no orphans)."""
    from sqlalchemy import select

    from app.models.instructor_comment import InstructorComment

    admin, learner = await _make_admin_and_learner(db_session)
    sub = Submission(
        user_id=learner.id, course_id=default_course_id, phase=1, task_no=1,
        content="x", submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add(
        InstructorComment(submission_id=sub.id, author_user_id=admin.id, body="x")
    )
    await db_session.commit()

    await db_session.delete(sub)
    await db_session.commit()
    remaining = (
        await db_session.execute(select(InstructorComment))
    ).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_notification_round_trips_and_defaults_unread(db_session):
    from app.models.notification import Notification

    admin, learner = await _make_admin_and_learner(db_session)
    await db_session.commit()

    note = Notification(
        recipient_user_id=learner.id,
        sender_user_id=admin.id,
        title="Phase 1 完了おめでとう",
        body="次のフェーズに進めます",
        link="/phases/2",
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    assert note.id is not None
    # A freshly created notification is unread; read_at is set later via the
    # mark-read endpoint, never at insert time.
    assert note.read_at is None
    assert note.title == "Phase 1 完了おめでとう"


@pytest.mark.asyncio
async def test_notification_link_is_optional(db_session):
    from app.models.notification import Notification

    admin, learner = await _make_admin_and_learner(db_session)
    await db_session.commit()

    note = Notification(
        recipient_user_id=learner.id,
        sender_user_id=admin.id,
        title="お知らせ",
        body="本文",
        link=None,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    assert note.link is None
