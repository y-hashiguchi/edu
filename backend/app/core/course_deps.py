"""Sprint 7 — FastAPI dependency that resolves ?course= to a CourseContext.

Behavior:
- ?course= missing -> DEFAULT_COURSE_SLUG ('ai-driven-dev')
- Unknown slug -> 404
- Non-admin without active enrollment -> 403
- Admin without enrollment -> allowed (enrollment=None) for support views

Note: this dependency is intentionally separate from the
`enrollment` service so route code can introspect both course
(CourseData) and enrollment (DB row) without re-fetching."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.data.courses import (
    DEFAULT_COURSE_SLUG,
    CourseData,
    CourseNotFoundError as RegistryCourseNotFoundError,
    get_course as get_course_from_registry,
)
from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.user import User
from app.services.enrollment import (
    EnrollmentNotFoundError,
    _get_course_by_slug,
    require_active_enrollment,
)


@dataclass(frozen=True)
class CourseContext:
    course: CourseData
    enrollment: Enrollment | None


async def get_course_context(
    course: str | None = Query(None, alias="course"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CourseContext:
    slug = course or DEFAULT_COURSE_SLUG
    try:
        course_data = get_course_from_registry(slug)
    except RegistryCourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"course {e.slug!r} not found",
        ) from e

    db_course = await _get_course_by_slug(db, slug)

    if user.is_admin:
        return CourseContext(course=course_data, enrollment=None)

    try:
        enr = await require_active_enrollment(
            db, user_id=user.id, course_id=db_course.id
        )
    except EnrollmentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not enrolled in this course",
        ) from e

    return CourseContext(course=course_data, enrollment=enr)
