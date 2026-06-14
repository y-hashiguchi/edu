"""Sprint 7 — enrollment domain service.

Routes interact with enrollments only through these functions so the
course_slug -> course_id mapping is centralised. Admins bypass
require_active_enrollment in `app/core/course_deps.py` (this module
stays unaware of admin-ness)."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses import COURSE_REGISTRY
from app.models.course import Course
from app.models.enrollment import Enrollment

logger = logging.getLogger(__name__)


class CourseNotFoundError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course {slug!r} not found")
        self.slug = slug


class EnrollmentNotFoundError(Exception):
    def __init__(self, user_id: uuid.UUID, course_id: uuid.UUID) -> None:
        super().__init__(
            f"active enrollment for user={user_id} course={course_id} not found"
        )
        self.user_id = user_id
        self.course_id = course_id


class AlreadyEnrolledError(Exception):
    def __init__(self, user_id: uuid.UUID, course_slug: str) -> None:
        super().__init__(
            f"user={user_id} already enrolled in {course_slug!r}"
        )


@dataclass(frozen=True)
class MyCourseProjection:
    slug: str
    title: str
    description: str | None
    status: str


async def _get_course_by_slug(db: AsyncSession, slug: str) -> Course:
    if slug not in COURSE_REGISTRY:
        raise CourseNotFoundError(slug)
    result = await db.execute(select(Course).where(Course.slug == slug))
    course = result.scalar_one_or_none()
    if course is None:
        logger.warning(
            "course slug %r is in COURSE_REGISTRY but missing from DB — "
            "run alembic upgrade head",
            slug,
        )
        raise CourseNotFoundError(slug)
    return course


async def enroll_user(
    db: AsyncSession, *, user_id: uuid.UUID, course_slug: str
) -> Enrollment:
    course = await _get_course_by_slug(db, course_slug)
    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AlreadyEnrolledError(user_id, course_slug)

    enr = Enrollment(user_id=user_id, course_id=course.id, status="active")
    db.add(enr)
    await db.flush()
    return enr


async def require_active_enrollment(
    db: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> Enrollment:
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id,
            Enrollment.status == "active",
        )
    )
    enr = result.scalar_one_or_none()
    if enr is None:
        raise EnrollmentNotFoundError(user_id, course_id)
    return enr


async def list_my_courses(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[MyCourseProjection]:
    result = await db.execute(
        select(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user_id)
        .order_by(Course.sort_order, Course.title)
    )
    out: list[MyCourseProjection] = []
    for enr, course in result.all():
        out.append(
            MyCourseProjection(
                slug=course.slug,
                title=course.title,
                description=course.description,
                status=enr.status,
            )
        )
    return out
