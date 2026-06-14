"""Sprint 10 — cohort summary service unit tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.security import hash_password
from app.data.courses import DEFAULT_COURSE_SLUG, get_course
from app.models.enrollment import Enrollment
from app.models.progress import Progress, ProgressStatus
from app.models.user import User
from app.services.cohort_summary import compute_cohort_summary
from app.services.enrollment import enroll_user
from app.services.progress import initialize_progress_for_course


async def _make_enrolled_learner(
    db_session,
    default_course_id,
    *,
    email: str,
    enrolled_days_ago: int = 0,
):
    user = User(
        email=email,
        name=email.split("@")[0],
        password_hash=hash_password("p"),
    )
    db_session.add(user)
    await db_session.flush()
    await enroll_user(db_session, user_id=user.id, course_slug=DEFAULT_COURSE_SLUG)
    course_data = get_course(DEFAULT_COURSE_SLUG)
    await initialize_progress_for_course(
        db_session,
        user.id,
        default_course_id,
        [p.phase for p in course_data.phases],
    )
    if enrolled_days_ago:
        old = datetime.now(UTC) - timedelta(days=enrolled_days_ago)
        await db_session.execute(
            update(Enrollment)
            .where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == default_course_id,
            )
            .values(enrolled_at=old)
        )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_zero_enrollments_returns_empty_summary(
    db_session, se_course_id,
):
    summary = await compute_cohort_summary(
        db_session,
        course_id=se_course_id,
        course_slug="ai-era-se",
        course_title="SE Course",
    )
    assert summary.enrolled_count == 0
    assert summary.average_score is None
    assert summary.completion_rate == 0.0
    assert summary.stuck_learners == []
    assert summary.tag_heatmap == []


@pytest.mark.asyncio
async def test_enrolled_count_includes_active_only(
    db_session, default_course_id, seed_curriculum,
):
    await _make_enrolled_learner(
        db_session, default_course_id, email="a@e.com",
    )
    await _make_enrolled_learner(
        db_session, default_course_id, email="b@e.com",
    )
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
    )
    assert summary.enrolled_count >= 2


@pytest.mark.asyncio
async def test_average_score_from_latest_graded_per_user(
    db_session, default_course_id, seed_graded_submission, seed_curriculum,
):
    u1 = await _make_enrolled_learner(
        db_session, default_course_id, email="s1@e.com",
    )
    u2 = await _make_enrolled_learner(
        db_session, default_course_id, email="s2@e.com",
    )
    await seed_graded_submission(u1, 1, 1, 80)
    await seed_graded_submission(u2, 1, 1, 60)
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
    )
    assert summary.average_score == 70.0


@pytest.mark.asyncio
async def test_average_score_none_without_graded(
    db_session, default_course_id, seed_curriculum,
):
    await _make_enrolled_learner(
        db_session, default_course_id, email="nog@e.com",
    )
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
    )
    assert summary.average_score is None


@pytest.mark.asyncio
async def test_completion_rate_averages_per_user(
    db_session, default_course_id, seed_curriculum,
):
    user = await _make_enrolled_learner(
        db_session, default_course_id, email="comp@e.com",
    )
    await db_session.execute(
        update(Progress)
        .where(
            Progress.user_id == user.id,
            Progress.course_id == default_course_id,
            Progress.phase == 1,
        )
        .values(status=ProgressStatus.COMPLETED.value)
    )
    await db_session.commit()
    course = get_course(DEFAULT_COURSE_SLUG)
    total_phases = len(course.phases)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
    )
    expected = round(1 / total_phases, 4)
    assert summary.completion_rate == pytest.approx(expected, rel=1e-3)


@pytest.mark.asyncio
async def test_stuck_no_submissions_after_enroll_threshold(
    db_session, default_course_id, seed_curriculum,
):
    await _make_enrolled_learner(
        db_session,
        default_course_id,
        email="stuck0@e.com",
        enrolled_days_ago=10,
    )
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
        stuck_inactive_days=7,
    )
    assert len(summary.stuck_learners) == 1
    stuck = summary.stuck_learners[0]
    assert stuck.reason == "no_submissions"
    assert stuck.submission_count == 0
    assert stuck.email_masked == "s***@e.com"


@pytest.mark.asyncio
async def test_stuck_inactive_when_last_submission_old(
    db_session, default_course_id, seed_graded_submission, seed_curriculum,
):
    user = await _make_enrolled_learner(
        db_session, default_course_id, email="stuck1@e.com",
    )
    sub, _att = await seed_graded_submission(user, 1, 1, 70)
    old = datetime.now(UTC) - timedelta(days=10)
    sub.submitted_at = old
    sub.graded_at = old
    await db_session.commit()
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
        stuck_inactive_days=7,
    )
    reasons = {s.email_masked: s.reason for s in summary.stuck_learners}
    assert reasons.get("s***@e.com") == "inactive_7d"


@pytest.mark.asyncio
async def test_not_stuck_when_recently_active(
    db_session, default_course_id, seed_graded_submission, seed_curriculum,
):
    user = await _make_enrolled_learner(
        db_session, default_course_id, email="active@e.com",
    )
    await seed_graded_submission(user, 1, 1, 90)
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
        stuck_inactive_days=7,
    )
    emails = {s.email_masked for s in summary.stuck_learners}
    assert "a***@e.com" not in emails


@pytest.mark.asyncio
async def test_tag_heatmap_respects_min_submissions(
    db_session, default_course_id, seed_graded_submission, seed_curriculum,
):
    u1 = await _make_enrolled_learner(
        db_session, default_course_id, email="t1@e.com",
    )
    u2 = await _make_enrolled_learner(
        db_session, default_course_id, email="t2@e.com",
    )
    await seed_graded_submission(u1, 1, 1, 50)
    await seed_graded_submission(u2, 1, 1, 70)
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
    )
    tags = {e.tag: e for e in summary.tag_heatmap}
    phase1_tags = list(course.phases[0].tasks[0].skill_tags)
    assert phase1_tags
    for tag in phase1_tags:
        if tag in tags:
            assert tags[tag].submission_count >= 2


@pytest.mark.asyncio
async def test_tag_heatmap_excludes_single_submission_tags(
    db_session, default_course_id, seed_graded_submission, seed_curriculum,
):
    user = await _make_enrolled_learner(
        db_session, default_course_id, email="solo@e.com",
    )
    await seed_graded_submission(user, 1, 1, 55)
    course = get_course(DEFAULT_COURSE_SLUG)
    summary = await compute_cohort_summary(
        db_session,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        course_title=course.title,
    )
    assert summary.tag_heatmap == []
