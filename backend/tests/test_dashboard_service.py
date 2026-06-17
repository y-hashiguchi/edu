"""Sprint 5 dashboard orchestrator.

Mocks all 4 sub-services so the orchestrator's only responsibility under
test is correct gluing: pass weakness output into nudge input, drop a
section to its empty form when its sub-service raises, never let one
sub-service take down the whole response."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.security import hash_password
from app.data.courses import DEFAULT_COURSE_SLUG
from app.models.user import User
from app.services.dashboard import compose_dashboard
from app.services.nudge import NudgeResult
from app.services.progress_summary import ProgressSummary
from app.services.recommendation import Recommendation
from app.services.weakness import TagAverage, WeaknessResult


async def _make_user(db_session):
    user = User(email="d@e.com", name="D", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_happy_path_aggregates_four_sections(
    db_session,
    monkeypatch,
    default_course_id,
):
    user = await _make_user(db_session)

    monkeypatch.setattr(
        "app.services.dashboard.compute_weakness",
        AsyncMock(
            return_value=WeaknessResult(
                has_enough_data=True,
                top_weaknesses=[
                    TagAverage(tag="AI協調", average_score=60.0, submission_count=3),
                ],
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_progress_summary",
        AsyncMock(
            return_value=ProgressSummary(
                completed_tasks=5,
                total_tasks=12,
                submission_count=5,
                average_score=70.0,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_recommendations",
        AsyncMock(
            return_value=[
                Recommendation(
                    phase=2,
                    task_no=1,
                    title="t",
                    skill_tags=["AI協調"],
                    match_tag="AI協調",
                    rag_score=0.8,
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboard.get_or_generate",
        AsyncMock(
            return_value=NudgeResult(
                body="次は Phase 2 task 1。",
                generated_at=datetime.now(UTC),
                is_fresh=True,
            )
        ),
    )

    out = await compose_dashboard(
        db_session,
        claude=object(),
        embedding_client=object(),
        user_id=user.id,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
    )
    assert out.progress_summary.completed_tasks == 5
    assert out.weakness.has_enough_data is True
    assert len(out.recommendations) == 1
    assert out.nudge.is_fresh is True


@pytest.mark.asyncio
async def test_recommendation_failure_returns_empty_section_not_500(
    db_session,
    monkeypatch,
    default_course_id,
):
    user = await _make_user(db_session)
    monkeypatch.setattr(
        "app.services.dashboard.compute_weakness",
        AsyncMock(
            return_value=WeaknessResult(
                has_enough_data=True,
                top_weaknesses=[TagAverage(tag="AI協調", average_score=60.0, submission_count=3)],
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_progress_summary",
        AsyncMock(
            return_value=ProgressSummary(
                completed_tasks=5,
                total_tasks=12,
                submission_count=5,
                average_score=70.0,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_recommendations",
        AsyncMock(side_effect=RuntimeError("rag down")),
    )
    monkeypatch.setattr(
        "app.services.dashboard.get_or_generate",
        AsyncMock(
            return_value=NudgeResult(
                body="x",
                generated_at=datetime.now(UTC),
                is_fresh=True,
            )
        ),
    )

    out = await compose_dashboard(
        db_session,
        claude=object(),
        embedding_client=object(),
        user_id=user.id,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
    )
    assert out.recommendations == []
    assert out.progress_summary.completed_tasks == 5


@pytest.mark.asyncio
async def test_nudge_failure_returns_fallback_not_500(db_session, monkeypatch, default_course_id):
    user = await _make_user(db_session)
    monkeypatch.setattr(
        "app.services.dashboard.compute_weakness",
        AsyncMock(
            return_value=WeaknessResult(
                has_enough_data=False,
                top_weaknesses=[],
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_progress_summary",
        AsyncMock(
            return_value=ProgressSummary(
                completed_tasks=1,
                total_tasks=12,
                submission_count=1,
                average_score=None,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_recommendations",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.dashboard.get_or_generate",
        AsyncMock(side_effect=RuntimeError("anthropic down")),
    )

    out = await compose_dashboard(
        db_session,
        claude=object(),
        embedding_client=object(),
        user_id=user.id,
        course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
    )
    assert out.nudge.body
    assert out.nudge.is_fresh is False
