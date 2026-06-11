"""Sprint 7 — /api/me/dashboard must scope by course.

conftest.db_session re-seeds both `ai-driven-dev` and `ai-era-se`
Course rows from COURSE_REGISTRY before each test, so tests here look
up courses by slug rather than constructing them inline.
"""

import pytest
from sqlalchemy import select

from app.models.course import Course
from app.models.enrollment import Enrollment


async def _enroll(db, user_id, course_id):
    db.add(Enrollment(user_id=user_id, course_id=course_id, status="active"))
    await db.commit()


async def _get_course(db, slug):
    return (await db.execute(select(Course).where(Course.slug == slug))).scalar_one()


@pytest.mark.asyncio
async def test_dashboard_requires_active_enrollment(
    client, auth_user, auth_token, db_session
):
    # No enrollment for ai-era-se -> 403 (conftest already seeded the
    # Course row; auth_user is enrolled in ai-driven-dev only).
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/me/dashboard?course=ai-era-se")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_returns_default_course_when_param_missing(
    client, auth_user, auth_token, db_session
):
    # auth_user fixture enrolls in ai-driven-dev automatically.
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
    se = await _get_course(db_session, "ai-era-se")
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
