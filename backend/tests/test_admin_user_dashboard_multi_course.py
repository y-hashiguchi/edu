"""Sprint 7 — /api/admin/users/{id}/dashboard course scoping."""

import pytest

from app.models.course import Course
from app.models.enrollment import Enrollment


async def _seed(db, learner_id):
    from sqlalchemy import select

    se = (await db.execute(select(Course).where(Course.slug == "ai-era-se"))).scalar_one()
    db.add(Enrollment(user_id=learner_id, course_id=se.id, status="active"))
    await db.commit()
    return se


@pytest.mark.asyncio
async def test_admin_can_view_any_course_dashboard_without_enrollment(
    client, auth_user, admin_token, db_session
):
    """admin is_admin=True bypasses require_active_enrollment in CourseContext."""
    se = await _seed(db_session, auth_user.id)

    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get(
        f"/api/admin/users/{auth_user.id}/dashboard?course=ai-era-se"
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_admin_dashboard_unknown_course_returns_404(
    client, auth_user, admin_token
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get(
        f"/api/admin/users/{auth_user.id}/dashboard?course=nope"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_dashboard_default_course_when_param_missing(
    client, auth_user, admin_token
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get(f"/api/admin/users/{auth_user.id}/dashboard")
    assert res.status_code == 200
