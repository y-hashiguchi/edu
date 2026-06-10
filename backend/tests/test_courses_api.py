"""Sprint 7 — /api/courses (catalog + my courses) integration tests."""

import pytest

from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


async def _seed_courses(db):
    a = Course(slug="ai-driven-dev", title="AI Dev", description="d1", sort_order=0)
    b = Course(slug="ai-era-se", title="SE", description="d2", sort_order=1)
    db.add_all([a, b])
    await db.commit()
    return a, b


@pytest.mark.asyncio
async def test_catalog_is_public(client, db_session):
    await _seed_courses(db_session)
    res = client.get("/api/courses/catalog")
    assert res.status_code == 200
    body = res.json()
    slugs = [i["slug"] for i in body["items"]]
    assert "ai-driven-dev" in slugs
    assert "ai-era-se" in slugs


@pytest.mark.asyncio
async def test_catalog_sorted_by_sort_order(client, db_session):
    await _seed_courses(db_session)
    res = client.get("/api/courses/catalog")
    items = res.json()["items"]
    assert items[0]["slug"] == "ai-driven-dev"
    assert items[1]["slug"] == "ai-era-se"


@pytest.mark.asyncio
async def test_my_courses_requires_auth(client):
    res = client.get("/api/courses")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_my_courses_returns_enrolled_only(
    client, auth_user, auth_token, db_session
):
    a, b = await _seed_courses(db_session)
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=a.id, status="active")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/courses")
    assert res.status_code == 200
    slugs = [i["slug"] for i in res.json()["items"]]
    assert slugs == ["ai-driven-dev"]


@pytest.mark.asyncio
async def test_my_courses_includes_status(
    client, auth_user, auth_token, db_session
):
    a, _ = await _seed_courses(db_session)
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=a.id, status="paused")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/courses")
    assert res.json()["items"][0]["status"] == "paused"
