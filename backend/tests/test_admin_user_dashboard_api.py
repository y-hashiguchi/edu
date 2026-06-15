"""Sprint 6: GET /api/admin/users/{user_id}/dashboard — admin が任意の
受講者の dashboard を見られる。nudge セクションは含まれない。"""

from unittest.mock import AsyncMock

import pytest

from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.services.progress_summary import ProgressSummary
from app.services.recommendation import Recommendation
from app.services.weakness import TagAverage, WeaknessResult


def _auth(client, user_id):
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


async def _make_user(db_session, email, is_admin=False):
    user = User(
        email=email, name=email[:2], password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _stub_compose(monkeypatch):
    from app.services.dashboard import AdminDashboardData

    fake = AdminDashboardData(
        progress_summary=ProgressSummary(
            completed_tasks=5, total_tasks=12,
            submission_count=5, average_score=72.0,
        ),
        weakness=WeaknessResult(
            has_enough_data=True,
            top_weaknesses=[
                TagAverage(tag="AI協調", average_score=60.0, submission_count=3),
            ],
        ),
        recommendations=[
            Recommendation(
                phase=2, task_no=1, title="t",
                skill_tags=["AI協調"], match_tag="AI協調", rag_score=0.8,
            ),
        ],
    )
    monkeypatch.setattr(
        "app.api.admin.user_dashboard.compose_dashboard_for_admin",
        AsyncMock(return_value=fake),
    )


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client, db_session):
    learner = await _make_user(db_session, "l@e.com")
    assert client.get(f"/api/admin/users/{learner.id}/dashboard").status_code == 401


@pytest.mark.asyncio
async def test_non_admin_returns_403(client, db_session):
    learner = await _make_user(db_session, "l@e.com")
    other = await _make_user(db_session, "o@e.com")
    _auth(client, other.id)
    assert client.get(
        f"/api/admin/users/{learner.id}/dashboard"
    ).status_code == 403


@pytest.mark.asyncio
async def test_admin_can_fetch_any_learners_dashboard(
    client, db_session, admin_user, monkeypatch,
):
    learner = await _make_user(db_session, "l@e.com")
    _stub_compose(monkeypatch)
    _auth(client, admin_user.id)

    r = client.get(f"/api/admin/users/{learner.id}/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "progress_summary" in body
    assert "weakness" in body
    assert "recommendations" in body
    assert "nudge" not in body


@pytest.mark.asyncio
async def test_admin_dashboard_returns_404_for_unknown_user(
    client, db_session, admin_user, monkeypatch,
):
    import uuid as uuid_mod

    _stub_compose(monkeypatch)
    _auth(client, admin_user.id)
    r = client.get(f"/api/admin/users/{uuid_mod.uuid4()}/dashboard")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_dashboard_returns_404_for_admin_target(
    client, db_session, admin_user, monkeypatch,
):
    """Sprint 6 MED-6: admin 同士の dashboard 参照は 404。"""
    other_admin = await _make_user(db_session, "a2@e.com", is_admin=True)
    _stub_compose(monkeypatch)
    _auth(client, admin_user.id)
    r = client.get(f"/api/admin/users/{other_admin.id}/dashboard")
    assert r.status_code == 404
