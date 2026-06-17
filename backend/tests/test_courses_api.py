"""Sprint 7 — /api/courses (catalog + my courses) integration tests."""

import pytest
from sqlalchemy import select, update

from app.models.course import Course
from app.models.enrollment import Enrollment


async def _get_courses(db):
    """Sprint 7: conftest re-seeds the two real courses after every
    truncate; this helper just fetches them back."""
    res = await db.execute(select(Course).where(Course.slug.in_(["ai-driven-dev", "ai-era-se"])))
    rows = {c.slug: c for c in res.scalars().all()}
    return rows["ai-driven-dev"], rows["ai-era-se"]


@pytest.mark.asyncio
async def test_catalog_is_public(client, db_session):
    await _get_courses(db_session)
    res = client.get("/api/courses/catalog")
    assert res.status_code == 200
    body = res.json()
    slugs = [i["slug"] for i in body["items"]]
    assert "ai-driven-dev" in slugs
    assert "ai-era-se" in slugs


@pytest.mark.asyncio
async def test_catalog_sorted_by_sort_order(client, db_session):
    await _get_courses(db_session)
    res = client.get("/api/courses/catalog")
    items = res.json()["items"]
    assert items[0]["slug"] == "ai-driven-dev"
    assert items[1]["slug"] == "ai-era-se"


@pytest.mark.asyncio
async def test_catalog_ai_era_se_description_reflects_full_syllabus(client, db_session):
    await _get_courses(db_session)
    res = client.get("/api/courses/catalog")
    se = next(i for i in res.json()["items"] if i["slug"] == "ai-era-se")
    assert "4 フェーズ" in se["description"]
    assert "31 課題" in se["description"]


@pytest.mark.asyncio
async def test_my_courses_requires_auth(client):
    res = client.get("/api/courses")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_my_courses_returns_enrolled_only(client, auth_user, auth_token, db_session):
    # auth_user is already enrolled in ai-driven-dev (default course)
    # via the conftest fixture.
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/courses")
    assert res.status_code == 200
    slugs = [i["slug"] for i in res.json()["items"]]
    assert slugs == ["ai-driven-dev"]


@pytest.mark.asyncio
async def test_my_courses_includes_status(client, auth_user, auth_token, db_session):
    # auth_user is already enrolled in ai-driven-dev. Flip the row to
    # "paused" so we can verify the status surfaces through the API.
    await db_session.execute(
        update(Enrollment).where(Enrollment.user_id == auth_user.id).values(status="paused")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/courses")
    assert res.json()["items"][0]["status"] == "paused"
