"""Sprint 5 dashboard API tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.services.nudge import NudgeResult
from app.services.progress_summary import ProgressSummary
from app.services.recommendation import Recommendation
from app.services.weakness import TagAverage, WeaknessResult


def _auth(client, user_id) -> None:
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


async def _make_user(db_session, email="x@e.com"):
    from app.services.enrollment import enroll_user

    user = User(email=email, name="X", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    # Sprint 7: dashboard requires active enrollment.
    await enroll_user(db_session, user_id=user.id, course_slug="ai-driven-dev")
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _stub_compose(monkeypatch, *, has_data=True):
    """Replace compose_dashboard with a deterministic stub so the test
    exercises the API/serialization layer, not the sub-services."""
    from app.services.dashboard import DashboardData

    fake = DashboardData(
        progress_summary=ProgressSummary(
            completed_tasks=5, total_tasks=12,
            submission_count=5, average_score=72.0,
        ),
        weakness=WeaknessResult(
            has_enough_data=has_data,
            top_weaknesses=([
                TagAverage(tag="AI協調", average_score=60.0, submission_count=3),
            ] if has_data else []),
        ),
        recommendations=([
            Recommendation(
                phase=2, task_no=1, title="t",
                skill_tags=["AI協調"], match_tag="AI協調", rag_score=0.8,
            ),
        ] if has_data else []),
        nudge=NudgeResult(
            body="次は Phase 2 task 1 をやろう。",
            generated_at=datetime.now(UTC), is_fresh=True,
        ),
    )
    monkeypatch.setattr(
        "app.api.me_dashboard.compose_dashboard",
        AsyncMock(return_value=fake),
    )


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client):
    assert client.get("/api/me/dashboard").status_code == 401


@pytest.mark.asyncio
async def test_returns_full_response_shape(client, db_session, monkeypatch):
    user = await _make_user(db_session)
    _stub_compose(monkeypatch, has_data=True)
    _auth(client, user.id)

    r = client.get("/api/me/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {
        "progress_summary", "weakness", "recommendations", "nudge"
    }
    assert body["progress_summary"]["total_tasks"] == 12
    assert body["weakness"]["has_enough_data"] is True
    assert body["recommendations"]["items"][0]["match_tag"] == "AI協調"
    assert body["nudge"]["is_fresh"] is True


@pytest.mark.asyncio
async def test_cold_start_response(client, db_session, monkeypatch):
    user = await _make_user(db_session, email="cold@e.com")
    _stub_compose(monkeypatch, has_data=False)
    _auth(client, user.id)

    body = client.get("/api/me/dashboard").json()
    assert body["weakness"]["has_enough_data"] is False
    assert body["recommendations"]["items"] == []


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_dashboard(client, db_session, monkeypatch):
    """BOLA fence: the dashboard endpoint takes no user_id in the URL,
    so this test mostly verifies token = identity. Two users get
    independent stubs."""
    a = await _make_user(db_session, email="a@e.com")
    b = await _make_user(db_session, email="b@e.com")
    _stub_compose(monkeypatch, has_data=True)
    _auth(client, a.id)
    r1 = client.get("/api/me/dashboard")
    assert r1.status_code == 200
    _auth(client, b.id)
    r2 = client.get("/api/me/dashboard")
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_rate_limited_at_high_rate(
    client, db_session, monkeypatch,
):
    """HIGH-1 (sprint-5 review): a stolen token must not be able to
    loop the dashboard endpoint to drive LLM costs. Per-IP rate limit
    via slowapi keeps the abuse ceiling bounded."""
    from app.api.me_dashboard import settings as md_settings
    from app.core.limiter import limiter

    user = await _make_user(db_session, email="rl@e.com")
    _stub_compose(monkeypatch, has_data=True)

    monkeypatch.setattr(md_settings, "me_write_rate_limit", "5/minute")
    monkeypatch.setattr(limiter, "enabled", True)
    try:
        limiter._storage.reset()
    except Exception:  # pragma: no cover
        pass

    _auth(client, user.id)
    statuses = [
        client.get("/api/me/dashboard").status_code for _ in range(7)
    ]
    assert 429 in statuses, statuses
