"""Sprint 7 — course_deps dependency unit tests.

Tests exercise the dependency directly (no FastAPI request) so they
don't depend on conftest's not-yet-updated fixtures."""

import pytest
from fastapi import HTTPException

from app.core.course_deps import get_course_context
from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


async def _seed_user_and_course(db, *, is_admin=False, enrolled=True):
    """Sprint 7: conftest re-seeds the course rows; this helper only
    inserts the user + (optionally) the enrollment."""
    from sqlalchemy import select

    user = User(
        email="u@e.com", name="U", password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    course = (
        await db.execute(select(Course).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    if enrolled:
        db.add(Enrollment(user_id=user.id, course_id=course.id))
    await db.commit()
    await db.refresh(user)
    return user, course


@pytest.mark.asyncio
async def test_default_slug_resolves_when_unspecified(db_session):
    user, _ = await _seed_user_and_course(db_session)
    ctx = await get_course_context(course=None, user=user, db=db_session)
    assert ctx.course.slug == "ai-driven-dev"


@pytest.mark.asyncio
async def test_explicit_slug_resolves(db_session):
    user, _ = await _seed_user_and_course(db_session)
    ctx = await get_course_context(course="ai-driven-dev", user=user, db=db_session)
    assert ctx.course.slug == "ai-driven-dev"


@pytest.mark.asyncio
async def test_unknown_slug_returns_404(db_session):
    user, _ = await _seed_user_and_course(db_session)
    with pytest.raises(HTTPException) as ei:
        await get_course_context(course="nope", user=user, db=db_session)
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_without_enrollment_gets_403(db_session):
    user, _ = await _seed_user_and_course(db_session, enrolled=False)
    with pytest.raises(HTTPException) as ei:
        await get_course_context(course="ai-driven-dev", user=user, db=db_session)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_without_enrollment_passes(db_session):
    user, _ = await _seed_user_and_course(db_session, is_admin=True, enrolled=False)
    ctx = await get_course_context(course="ai-driven-dev", user=user, db=db_session)
    assert ctx.course.slug == "ai-driven-dev"
    assert ctx.enrollment is None
