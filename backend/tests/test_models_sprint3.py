"""Sprint 3 model sanity tests."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.user import User


async def _make_user(db) -> User:
    u = User(
        email=f"u-{uuid.uuid4()}@example.com",
        name="t",
        password_hash=hash_password("p"),
    )
    db.add(u)
    await db.flush()
    return u


async def _make_submission(db, user_id: uuid.UUID) -> Submission:
    s = Submission(user_id=user_id, phase=1, task_no=1, content="hello")
    db.add(s)
    await db.flush()
    return s


@pytest.mark.asyncio
async def test_submission_file_can_be_created(db_session):
    user = await _make_user(db_session)
    sub = await _make_submission(db_session, user.id)
    f = SubmissionFile(
        submission_id=sub.id,
        file_path="uploads/u/s/code.py",
        mime_type="text/x-python",
        size_bytes=1234,
    )
    db_session.add(f)
    await db_session.commit()
    await db_session.refresh(f)
    assert f.id is not None
    assert f.created_at is not None


@pytest.mark.asyncio
async def test_submission_file_cascades_on_submission_delete(db_session):
    from sqlalchemy import select

    user = await _make_user(db_session)
    sub = await _make_submission(db_session, user.id)
    db_session.add(
        SubmissionFile(
            submission_id=sub.id,
            file_path="uploads/u/s/a.txt",
            mime_type="text/plain",
            size_bytes=10,
        )
    )
    await db_session.commit()

    await db_session.delete(sub)
    await db_session.commit()

    remaining = (
        await db_session.execute(select(SubmissionFile))
    ).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_submission_file_requires_submission(db_session):
    f = SubmissionFile(
        submission_id=uuid.uuid4(),
        file_path="x",
        mime_type="text/plain",
        size_bytes=1,
    )
    db_session.add(f)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_grading_attempt_graded_row(db_session):
    from app.models.grading_attempt import GradingAttempt, GradingStatus

    user = await _make_user(db_session)
    sub = await _make_submission(db_session, user.id)
    attempt = GradingAttempt(
        submission_id=sub.id,
        status=GradingStatus.GRADED,
        score=85,
        feedback="Good",
        model_name="claude-sonnet-4-5",
    )
    db_session.add(attempt)
    await db_session.commit()
    await db_session.refresh(attempt)
    assert attempt.id is not None
    assert attempt.created_at is not None


@pytest.mark.asyncio
async def test_grading_attempt_failed_row(db_session):
    from app.models.grading_attempt import GradingAttempt, GradingStatus

    user = await _make_user(db_session)
    sub = await _make_submission(db_session, user.id)
    attempt = GradingAttempt(
        submission_id=sub.id,
        status=GradingStatus.FAILED,
        error_message="rate limit",
        model_name="claude-sonnet-4-5",
    )
    db_session.add(attempt)
    await db_session.commit()
    await db_session.refresh(attempt)
    assert attempt.status == GradingStatus.FAILED
    assert attempt.score is None


@pytest.mark.asyncio
async def test_grading_attempt_cascades_on_submission_delete(db_session):
    from sqlalchemy import select

    from app.models.grading_attempt import GradingAttempt, GradingStatus

    user = await _make_user(db_session)
    sub = await _make_submission(db_session, user.id)
    db_session.add(
        GradingAttempt(
            submission_id=sub.id,
            status=GradingStatus.GRADED,
            score=80,
            feedback="ok",
            model_name="claude-sonnet-4-5",
        )
    )
    await db_session.commit()
    await db_session.delete(sub)
    await db_session.commit()
    remaining = (
        await db_session.execute(select(GradingAttempt))
    ).scalars().all()
    assert remaining == []
