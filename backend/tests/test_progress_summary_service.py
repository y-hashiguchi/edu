"""Sprint 5: progress summary service.

Aggregates per-user submission count + completed-tasks count + average
score. Cold-start (submission_count < MIN_SUBMISSION_THRESHOLD) returns
average_score=None so the UI can render "—" instead of a placeholder
number that anchors expectations.

Sprint 7: compute_progress_summary now requires (course_id, course_slug)
so total_tasks reflects the right course's curriculum.
"""

import pytest

from app.core.security import hash_password
from app.data.courses import DEFAULT_COURSE_SLUG, get_course
from app.models.user import User
from app.services.progress_summary import (
    ProgressSummary,
    compute_progress_summary,
)


def _expected_total_tasks() -> int:
    return sum(len(p.tasks) for p in get_course(DEFAULT_COURSE_SLUG).phases)


async def _make_user(db_session, email="p@e.com"):
    user = User(email=email, name="P", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


def test_default_course_total_tasks_is_12():
    # ai-driven-dev curriculum is still 12 tasks (4 phases * 3 tasks).
    assert _expected_total_tasks() == 12


@pytest.mark.asyncio
async def test_empty_user_returns_zeros_and_null_average(
    db_session, default_course_id
):
    user = await _make_user(db_session)
    out = await compute_progress_summary(
        db_session, user.id, default_course_id, DEFAULT_COURSE_SLUG
    )
    assert isinstance(out, ProgressSummary)
    assert out.completed_tasks == 0
    assert out.total_tasks == _expected_total_tasks()
    assert out.submission_count == 0
    assert out.average_score is None


@pytest.mark.asyncio
async def test_below_threshold_returns_null_average(
    db_session, default_course_id, seed_graded_submission,
):
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 80)
    await seed_graded_submission(user, 1, 2, 90)

    out = await compute_progress_summary(
        db_session, user.id, default_course_id, DEFAULT_COURSE_SLUG
    )
    assert out.submission_count == 2
    assert out.average_score is None
    assert out.completed_tasks == 2


@pytest.mark.asyncio
async def test_above_threshold_returns_average_rounded(
    db_session, default_course_id, seed_graded_submission,
):
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 80)
    await seed_graded_submission(user, 1, 2, 70)
    await seed_graded_submission(user, 1, 3, 60)

    out = await compute_progress_summary(
        db_session, user.id, default_course_id, DEFAULT_COURSE_SLUG
    )
    assert out.submission_count == 3
    assert out.completed_tasks == 3
    assert out.average_score == 70.0
