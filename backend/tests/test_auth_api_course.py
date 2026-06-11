"""Sprint 7 — auth.register must require course_slug."""

import pytest
from sqlalchemy import select

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.progress import Progress
from app.models.user import User


async def _seed_courses(db):
    """Sprint 7: conftest already re-seeds the two real courses; this
    helper just fetches them back."""
    res = await db.execute(
        select(Course).where(Course.slug.in_(["ai-driven-dev", "ai-era-se"]))
    )
    rows = {c.slug: c for c in res.scalars().all()}
    return rows["ai-driven-dev"], rows["ai-era-se"]


@pytest.mark.asyncio
async def test_register_requires_course_slug(client, db_session):
    await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_unknown_slug(client, db_session):
    await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
            "course_slug": "nope",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_creates_enrollment(client, db_session):
    a, _ = await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
            "course_slug": "ai-era-se",
        },
    )
    assert res.status_code == 201
    user_id = res.json()["id"]

    enr = (
        await db_session.execute(
            select(Enrollment).where(Enrollment.user_id == user_id)
        )
    ).scalar_one()
    assert enr.status == "active"


@pytest.mark.asyncio
async def test_register_seeds_progress_for_chosen_course(client, db_session):
    a, b = await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
            "course_slug": "ai-era-se",
        },
    )
    user_id = res.json()["id"]
    rows = (
        await db_session.execute(
            select(Progress).where(Progress.user_id == user_id)
        )
    ).scalars().all()
    # ai-era-se has 1 phase (Phase 1 pilot)
    assert {r.phase for r in rows} == {1}
    assert all(r.course_id == b.id for r in rows)
