"""Sprint 6 model tests — InstructorComment.parent_id (thread support)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.instructor_comment import InstructorComment
from app.models.submission import Submission
from app.models.user import User


async def _make_user(db_session, email="u@e.com", is_admin=False):
    user = User(
        email=email, name="U", password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_submission(db_session, owner):
    sub = Submission(
        user_id=owner.id, phase=1, task_no=1,
        content="essay", submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


@pytest.mark.asyncio
async def test_instructor_comment_parent_id_defaults_null(db_session):
    """A trunk comment (admin's top-level post) has parent_id NULL."""
    admin = await _make_user(db_session, email="a@e.com", is_admin=True)
    owner = await _make_user(db_session, email="o@e.com")
    sub = await _make_submission(db_session, owner)

    trunk = InstructorComment(
        submission_id=sub.id,
        author_user_id=admin.id,
        body="great work",
    )
    db_session.add(trunk)
    await db_session.commit()
    await db_session.refresh(trunk)
    assert trunk.parent_id is None


@pytest.mark.asyncio
async def test_instructor_comment_reply_links_to_parent(db_session):
    admin = await _make_user(db_session, email="a@e.com", is_admin=True)
    owner = await _make_user(db_session, email="o@e.com")
    sub = await _make_submission(db_session, owner)

    trunk = InstructorComment(
        submission_id=sub.id, author_user_id=admin.id, body="trunk",
    )
    db_session.add(trunk)
    await db_session.flush()

    reply = InstructorComment(
        submission_id=sub.id, author_user_id=owner.id,
        body="thank you", parent_id=trunk.id,
    )
    db_session.add(reply)
    await db_session.commit()
    await db_session.refresh(reply)
    assert reply.parent_id == trunk.id


@pytest.mark.asyncio
async def test_instructor_comment_self_fk_cascades_on_parent_delete(db_session):
    """Deleting the trunk comment cascades to its replies — keeping
    orphan replies would leak threads visible in the admin index but
    inaccessible from the trunk."""
    admin = await _make_user(db_session, email="a@e.com", is_admin=True)
    owner = await _make_user(db_session, email="o@e.com")
    sub = await _make_submission(db_session, owner)

    trunk = InstructorComment(
        submission_id=sub.id, author_user_id=admin.id, body="trunk",
    )
    db_session.add(trunk)
    await db_session.flush()
    reply = InstructorComment(
        submission_id=sub.id, author_user_id=owner.id,
        body="reply", parent_id=trunk.id,
    )
    db_session.add(reply)
    await db_session.commit()

    await db_session.delete(trunk)
    await db_session.commit()
    leftover = (
        await db_session.execute(
            select(InstructorComment).where(InstructorComment.id == reply.id)
        )
    ).first()
    assert leftover is None
