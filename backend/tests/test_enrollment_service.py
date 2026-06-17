"""Sprint 7 — enrollment service unit tests."""

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.course import Course
from app.models.user import User
from app.services.enrollment import (
    AlreadyEnrolledError,
    CourseNotFoundError,
    EnrollmentNotFoundError,
    enroll_user,
    list_my_courses,
    require_active_enrollment,
)


async def _make_user(db, email="u@e.com", is_admin=False):
    user = User(
        email=email,
        name="U",
        password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)
    return user


async def _seed_courses(db):
    """Sprint 7: conftest now re-seeds the two real courses after every
    truncate, so this helper just fetches them back instead of inserting
    duplicates."""
    res = await db.execute(select(Course).where(Course.slug.in_(["ai-driven-dev", "ai-era-se"])))
    rows = {c.slug: c for c in res.scalars().all()}
    return rows["ai-driven-dev"], rows["ai-era-se"]


@pytest.mark.asyncio
async def test_enroll_user_creates_active_row(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)

    enr = await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()
    assert enr.status == "active"
    assert enr.course_id == a.id


@pytest.mark.asyncio
async def test_enroll_user_raises_on_unknown_slug(db_session):
    user = await _make_user(db_session)
    with pytest.raises(CourseNotFoundError):
        await enroll_user(db_session, user_id=user.id, course_slug="nope")


@pytest.mark.asyncio
async def test_enroll_user_raises_on_duplicate(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)

    await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()
    with pytest.raises(AlreadyEnrolledError):
        await enroll_user(db_session, user_id=user.id, course_slug=a.slug)


@pytest.mark.asyncio
async def test_require_active_enrollment_ok(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)
    await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()

    found = await require_active_enrollment(db_session, user_id=user.id, course_id=a.id)
    assert found.status == "active"


@pytest.mark.asyncio
async def test_require_active_enrollment_raises_when_missing(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)
    with pytest.raises(EnrollmentNotFoundError):
        await require_active_enrollment(db_session, user_id=user.id, course_id=a.id)


@pytest.mark.asyncio
async def test_require_active_enrollment_ignores_paused(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)
    enr = await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    enr.status = "paused"
    await db_session.commit()
    with pytest.raises(EnrollmentNotFoundError):
        await require_active_enrollment(db_session, user_id=user.id, course_id=a.id)


@pytest.mark.asyncio
async def test_list_my_courses_returns_active_sorted(db_session):
    a, b = await _seed_courses(db_session)
    user = await _make_user(db_session)
    await enroll_user(db_session, user_id=user.id, course_slug=b.slug)
    await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()

    items = await list_my_courses(db_session, user_id=user.id)
    # sort_order ascending: ai-driven-dev (0) before ai-era-se (1)
    assert [it.slug for it in items] == ["ai-driven-dev", "ai-era-se"]
