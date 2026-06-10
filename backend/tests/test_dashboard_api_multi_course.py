"""Sprint 7 — /api/me/dashboard must scope by course."""

import pytest

from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


async def _enroll(db, user_id, course_id):
    db.add(Enrollment(user_id=user_id, course_id=course_id, status="active"))
    await db.commit()


@pytest.mark.asyncio
async def test_dashboard_requires_active_enrollment(
    client, auth_user, auth_token, db_session
):
    # No enrollment for ai-era-se -> 403
    db_session.add(Course(slug="ai-era-se", title="SE", sort_order=1))
    await db_session.commit()
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/me/dashboard?course=ai-era-se")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_returns_default_course_when_param_missing(
    client, auth_user, auth_token, db_session
):
    # auth_user fixture enrolls in ai-driven-dev automatically (Task 16)
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/me/dashboard")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_unknown_course_returns_404(
    client, auth_user, auth_token
):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/me/dashboard?course=nope")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_data_isolated_per_course(
    client, auth_user, auth_token, db_session
):
    """Submissions in course A must not contribute to dashboard for course B."""
    # auth_user already enrolled in ai-driven-dev by fixture
    se = Course(slug="ai-era-se", title="SE", sort_order=1)
    db_session.add(se)
    await db_session.commit()
    await db_session.refresh(se)
    await _enroll(db_session, auth_user.id, se.id)

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    # Submit something to ai-driven-dev
    client.post(
        "/api/submissions?course=ai-driven-dev",
        json={"phase": 1, "task_no": 1, "content": "essay"},
    )
    # Dashboard for ai-era-se must show zero submissions
    res = client.get("/api/me/dashboard?course=ai-era-se")
    assert res.status_code == 200
    body = res.json()
    assert body["progress_summary"]["submission_count"] == 0
