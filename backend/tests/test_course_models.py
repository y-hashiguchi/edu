"""Sprint 7 model tests — Course / Enrollment."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


@pytest.mark.asyncio
async def test_course_persists_with_unique_slug(db_session):
    c = Course(
        slug="ai-driven-dev",
        title="AI駆動型開発 補足カリキュラム",
        description=None,
        sort_order=0,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    assert c.id is not None

    dup = Course(slug="ai-driven-dev", title="dup", sort_order=1)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_enrollment_links_user_to_course(db_session):
    user = User(email="u@e.com", name="U", password_hash=hash_password("p"))
    course = Course(slug="ai-era-se", title="SE", sort_order=1)
    db_session.add_all([user, course])
    await db_session.flush()

    enr = Enrollment(user_id=user.id, course_id=course.id)
    db_session.add(enr)
    await db_session.commit()
    await db_session.refresh(enr)
    assert enr.status == "active"
    assert enr.enrolled_at is not None


@pytest.mark.asyncio
async def test_enrollment_unique_user_course_pair(db_session):
    user = User(email="u@e.com", name="U", password_hash=hash_password("p"))
    course = Course(slug="c1", title="C1", sort_order=0)
    db_session.add_all([user, course])
    await db_session.flush()
    db_session.add(Enrollment(user_id=user.id, course_id=course.id))
    await db_session.commit()

    db_session.add(Enrollment(user_id=user.id, course_id=course.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_user_delete_cascades_enrollment(db_session):
    user = User(email="u@e.com", name="U", password_hash=hash_password("p"))
    course = Course(slug="c1", title="C1", sort_order=0)
    db_session.add_all([user, course])
    await db_session.flush()
    db_session.add(Enrollment(user_id=user.id, course_id=course.id))
    await db_session.commit()

    await db_session.delete(user)
    await db_session.commit()
    remaining = (
        await db_session.execute(select(Enrollment))
    ).scalars().all()
    assert remaining == []
