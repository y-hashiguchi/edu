"""Sprint 6: comment thread service.

post_reply の境界条件をすべてユニットで押さえる:
  - 親 comment が同 submission に属さない → InvalidParentError
  - submission が他人 → SubmissionNotFoundError
  - 親の先祖に admin が居ない → UnauthorizedThreadError
  - 上記すべて通って初めて InstructorComment 行を作成
"""

from datetime import UTC, datetime

import pytest

from app.core.security import hash_password
from app.models.instructor_comment import InstructorComment
from app.models.submission import Submission
from app.models.user import User
from app.services.comment import (
    InvalidParentError,
    SubmissionNotFoundError,
    UnauthorizedThreadError,
    _ancestor_has_admin,
    post_reply,
)


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


async def _make_submission(db_session, owner, course_id, task_no=1):
    sub = Submission(
        user_id=owner.id,
        course_id=course_id,
        phase=1,
        task_no=task_no,
        content="x",
        submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


@pytest.mark.asyncio
async def test_post_reply_happy_path(db_session, default_course_id):
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

    reply = await post_reply(
        db=db_session,
        submission_id=sub.id,
        learner_user_id=learner.id,
        parent_id=trunk.id,
        body="thanks!",
    )
    assert reply.parent_id == trunk.id
    assert reply.author_user_id == learner.id


@pytest.mark.asyncio
async def test_post_reply_rejects_parent_in_different_submission(db_session, default_course_id):
    """Parent comment が別 submission に属する場合は 400 相当 (InvalidParentError)."""
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

    trunk = InstructorComment(
        submission_id=sub_b.id,
        author_user_id=admin.id,
        body="trunk in B",
    )
    db_session.add(trunk)
    await db_session.commit()
    await db_session.refresh(trunk)

    with pytest.raises(InvalidParentError):
        await post_reply(
            db=db_session,
            submission_id=sub_a.id,
            learner_user_id=learner.id,
            parent_id=trunk.id,
            body="oops",
        )


@pytest.mark.asyncio
async def test_post_reply_rejects_others_submission(db_session, default_course_id):
    """Sprint 4 と一貫: 他人の submission に対する操作は SubmissionNotFoundError
    (router 層で 404 にマップ、403 ではなく)."""
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

    with pytest.raises(SubmissionNotFoundError):
        await post_reply(
            db=db_session,
            submission_id=sub.id,
            learner_user_id=intruder.id,
            parent_id=trunk.id,
            body="evil",
        )


@pytest.mark.asyncio
async def test_post_reply_rejects_thread_with_no_admin_ancestor(db_session, default_course_id):
    """先祖に admin が居ないスレッドへの返信は UnauthorizedThreadError."""
    learner = await _make_user(db_session, "l@e.com")
    sub = await _make_submission(db_session, learner, default_course_id)

    fake_trunk = InstructorComment(
        submission_id=sub.id,
        author_user_id=learner.id,
        body="learner posted directly (shouldn't happen via API)",
    )
    db_session.add(fake_trunk)
    await db_session.commit()
    await db_session.refresh(fake_trunk)

    with pytest.raises(UnauthorizedThreadError):
        await post_reply(
            db=db_session,
            submission_id=sub.id,
            learner_user_id=learner.id,
            parent_id=fake_trunk.id,
            body="reply",
        )


@pytest.mark.asyncio
async def test_ancestor_has_admin_returns_true_for_admin_trunk(db_session, default_course_id):
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

    assert await _ancestor_has_admin(db_session, trunk.id) is True
