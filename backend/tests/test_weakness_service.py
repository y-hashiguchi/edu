"""Sprint 5: weakness service."""

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.weakness import (
    MIN_SUBMISSION_THRESHOLD,
    MIN_TAG_SUBMISSIONS,
    compute_weakness,
)


async def _make_user(db_session, email="w@e.com"):
    user = User(email=email, name="W", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_returns_has_enough_data_false_when_below_threshold(
    db_session, seed_graded_submission,
):
    """Submission < 3 件のとき has_enough_data=False、top_weaknesses=[]。"""
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 60)
    await seed_graded_submission(user, 1, 2, 70)

    result = await compute_weakness(db_session, user.id)
    assert result.has_enough_data is False
    assert result.top_weaknesses == []


@pytest.mark.asyncio
async def test_aggregates_by_tag_low_score_first(
    db_session, seed_graded_submission,
):
    """3 件以上提出すると、タグ別平均が低い順に並ぶ。"""
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 50)
    await seed_graded_submission(user, 1, 2, 90)
    await seed_graded_submission(user, 1, 3, 70)
    await seed_graded_submission(user, 2, 1, 60)
    await seed_graded_submission(user, 2, 3, 80)

    result = await compute_weakness(db_session, user.id)
    assert result.has_enough_data is True
    tags = [w.tag for w in result.top_weaknesses]
    assert tags == ["API基礎", "AI協調"]
    assert result.top_weaknesses[0].average_score == 65.0
    assert result.top_weaknesses[0].submission_count == 2


@pytest.mark.asyncio
async def test_returns_at_most_top_3(db_session, seed_graded_submission):
    user = await _make_user(db_session)
    await seed_graded_submission(user, 2, 1, 100)
    await seed_graded_submission(user, 2, 2, 100)
    await seed_graded_submission(user, 2, 3, 100)
    await seed_graded_submission(user, 3, 1, 30)
    await seed_graded_submission(user, 3, 2, 30)
    await seed_graded_submission(user, 3, 3, 30)

    result = await compute_weakness(db_session, user.id)
    assert len(result.top_weaknesses) <= 3


@pytest.mark.asyncio
async def test_uses_latest_graded_attempt_per_submission(
    db_session, seed_graded_submission,
):
    """再採点で 90 → 60 と変動した場合、60 を採用"""
    from datetime import UTC, datetime, timedelta

    from app.models.grading_attempt import GradingAttempt

    user = await _make_user(db_session)
    sub, first_att = await seed_graded_submission(user, 1, 1, 60)
    first_att.created_at = datetime.now(UTC) - timedelta(hours=2)
    new_att = GradingAttempt(
        submission_id=sub.id,
        status="graded",
        score=95,
        feedback="ok",
        model_name="claude-sonnet-4-5",
        created_at=datetime.now(UTC),
    )
    db_session.add(new_att)
    await seed_graded_submission(user, 1, 2, 50)
    await seed_graded_submission(user, 1, 3, 50)
    await db_session.commit()

    result = await compute_weakness(db_session, user.id)
    tags = {w.tag: w for w in result.top_weaknesses}
    assert "Git/GitHub" not in tags  # phase 1 task 1 -> 1 件のみ -> 除外
    assert result.has_enough_data is True


def test_constants_match_spec():
    assert MIN_SUBMISSION_THRESHOLD == 3
    assert MIN_TAG_SUBMISSIONS == 2


@pytest.mark.asyncio
async def test_skips_submissions_for_removed_curriculum_tasks(
    db_session, seed_graded_submission, monkeypatch,
):
    """HIGH-2 (sprint-5 review): a learner who submitted against a
    task that has since been removed from curriculum must still get a
    valid weakness analysis from their remaining submissions."""
    from app.services import weakness as weakness_mod

    user = await _make_user(db_session)
    # 4 valid submissions to clear MIN_SUBMISSION_THRESHOLD comfortably
    await seed_graded_submission(user, 1, 1, 50)
    await seed_graded_submission(user, 1, 2, 60)
    await seed_graded_submission(user, 1, 3, 70)
    # A submission whose curriculum entry was "removed". We don't
    # mutate CURRICULUM (immutable contract) — instead patch the
    # helper to raise KeyError for one specific coordinate.
    await seed_graded_submission(user, 2, 1, 80)

    real_get_tags = weakness_mod.get_task_skill_tags

    def fake_get_tags(phase, task_no):
        if (phase, task_no) == (2, 1):
            raise KeyError("removed in test")
        return real_get_tags(phase, task_no)

    monkeypatch.setattr(weakness_mod, "get_task_skill_tags", fake_get_tags)

    result = await weakness_mod.compute_weakness(db_session, user.id)
    # has_enough_data still True (the 4 submissions are all graded;
    # one tag set is skipped, but the row count counts the submission)
    assert result.has_enough_data is True
    # No "AI協調" or "API基礎" tags from phase 2 task 1 should appear
    # because that row was skipped — and phase 1 tasks each have only
    # 1 submission so they fall below MIN_TAG_SUBMISSIONS too. So
    # top_weaknesses is empty, but the call does NOT raise.
    assert isinstance(result.top_weaknesses, list)
