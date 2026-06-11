"""Sprint 7 LOW-2 — POST /api/admin/users/{user_id}/enrollments."""

import pytest
from sqlalchemy import select

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.progress import Progress


@pytest.mark.asyncio
async def test_admin_enroll_requires_admin(client, auth_user, auth_token):
    """A non-admin learner must not be able to enroll others."""
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.post(
        f"/api/admin/users/{auth_user.id}/enrollments",
        json={"course_slug": "ai-era-se"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_enroll_rejects_unknown_slug(
    client, auth_user, admin_token
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post(
        f"/api/admin/users/{auth_user.id}/enrollments",
        json={"course_slug": "nope"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_admin_enroll_returns_404_when_user_unknown(
    client, admin_token
):
    import uuid as uuidlib

    ghost = uuidlib.uuid4()
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post(
        f"/api/admin/users/{ghost}/enrollments",
        json={"course_slug": "ai-era-se"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_enroll_409_when_already_enrolled(
    client, auth_user, admin_token, db_session
):
    """auth_user is already enrolled in ai-driven-dev by the fixture."""
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post(
        f"/api/admin/users/{auth_user.id}/enrollments",
        json={"course_slug": "ai-driven-dev"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_admin_enroll_adds_course_and_seeds_progress(
    client, auth_user, admin_token, db_session
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post(
        f"/api/admin/users/{auth_user.id}/enrollments",
        json={"course_slug": "ai-era-se"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["course_slug"] == "ai-era-se"
    assert body["status"] == "active"

    # Enrollment row exists
    se = (
        await db_session.execute(
            select(Course).where(Course.slug == "ai-era-se")
        )
    ).scalar_one()
    enr = (
        await db_session.execute(
            select(Enrollment).where(
                Enrollment.user_id == auth_user.id,
                Enrollment.course_id == se.id,
            )
        )
    ).scalar_one()
    assert enr.status == "active"

    # Progress was seeded for ai-era-se Phase 1
    se_progress = (
        await db_session.execute(
            select(Progress).where(
                Progress.user_id == auth_user.id,
                Progress.course_id == se.id,
            )
        )
    ).scalars().all()
    assert {p.phase for p in se_progress} == {1}
