"""Sprint 16 — admin course create / delete tests."""

import pytest
from sqlalchemy import select

from app.data.courses import get_course, runtime
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.enrollment import Enrollment
from app.services.curriculum_course import (
    CourseHasEnrollmentsError,
    ProtectedCourseError,
    add_course,
    delete_course,
)
from app.services.enrollment import enroll_user


@pytest.mark.asyncio
async def test_add_course_scaffolds_phases(db_session):
    result = await add_course(
        db_session,
        slug="test-course",
        title="Test Course",
        description="desc",
    )
    await db_session.commit()
    await runtime.reload_course(db_session, "test-course")

    assert result.slug == "test-course"
    assert result.phase_count == 4

    phases = (
        await db_session.execute(
            select(CurriculumPhase)
            .join(Course)
            .where(Course.slug == "test-course")
            .order_by(CurriculumPhase.phase_no)
        )
    ).scalars().all()
    assert len(phases) == 4
    assert phases[0].phase_no == 1

    cached = get_course("test-course")
    assert cached.title == "Test Course"
    assert len(cached.phases) == 4
    assert len(cached.phases[0].tasks) == 1


@pytest.mark.asyncio
async def test_delete_course_removes_rows(db_session):
    await add_course(db_session, slug="tmp-course", title="Tmp")
    await db_session.commit()
    await runtime.reload_course(db_session, "tmp-course")

    await delete_course(db_session, slug="tmp-course")
    await db_session.commit()
    runtime.evict_course("tmp-course")

    row = (
        await db_session.execute(select(Course).where(Course.slug == "tmp-course"))
    ).scalar_one_or_none()
    assert row is None


@pytest.mark.asyncio
async def test_delete_protected_course_raises(db_session):
    with pytest.raises(ProtectedCourseError):
        await delete_course(db_session, slug="ai-driven-dev")


@pytest.mark.asyncio
async def test_delete_course_with_enrollment_raises(db_session, auth_user):
    await add_course(db_session, slug="enrolled-course", title="E")
    await db_session.commit()
    await enroll_user(db_session, user_id=auth_user.id, course_slug="enrolled-course")
    await db_session.commit()

    with pytest.raises(CourseHasEnrollmentsError):
        await delete_course(db_session, slug="enrolled-course")
