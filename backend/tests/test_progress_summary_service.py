"""Sprint 5: progress summary service.

Aggregates per-user submission count + completed-tasks count + average
score. Cold-start (submission_count < MIN_SUBMISSION_THRESHOLD) returns
average_score=None so the UI can render "—" instead of a placeholder
number that anchors expectations.
"""

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.progress_summary import (
    TOTAL_TASKS,
    ProgressSummary,
    compute_progress_summary,
)


async def _make_user(db_session, email="p@e.com"):
    user = User(email=email, name="P", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


def test_total_tasks_constant_is_12():
    assert TOTAL_TASKS == 12


@pytest.mark.asyncio
async def test_empty_user_returns_zeros_and_null_average(db_session):
    user = await _make_user(db_session)
    out = await compute_progress_summary(db_session, user.id)
    assert isinstance(out, ProgressSummary)
    assert out.completed_tasks == 0
    assert out.total_tasks == 12
    assert out.submission_count == 0
    assert out.average_score is None


@pytest.mark.asyncio
async def test_below_threshold_returns_null_average(
    db_session, seed_graded_submission,
):
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 80)
    await seed_graded_submission(user, 1, 2, 90)

    out = await compute_progress_summary(db_session, user.id)
    assert out.submission_count == 2
    assert out.average_score is None
    assert out.completed_tasks == 2


@pytest.mark.asyncio
async def test_above_threshold_returns_average_rounded(
    db_session, seed_graded_submission,
):
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 80)
    await seed_graded_submission(user, 1, 2, 70)
    await seed_graded_submission(user, 1, 3, 60)

    out = await compute_progress_summary(db_session, user.id)
    assert out.submission_count == 3
    assert out.completed_tasks == 3
    assert out.average_score == 70.0
