"""Sprint 10 — admin cohort summary API."""

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin_cohort import (
    AdminCohortSummaryOut,
    StuckLearnerOut,
    TagHeatmapEntryOut,
)
from app.services.cohort_summary import compute_cohort_summary
from app.services.enrollment import CourseNotFoundError, _get_course_by_slug

router = APIRouter(prefix="/api/admin/courses", tags=["admin"])

_SLUG_PATTERN = r"^[a-z0-9_-]{1,80}$"


@router.get(
    "/{course_slug}/cohort-summary",
    response_model=AdminCohortSummaryOut,
)
@limiter.limit(lambda: settings.admin_cohort_rate_limit)
async def get_cohort_summary(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCohortSummaryOut:
    try:
        course = await _get_course_by_slug(db, course_slug)
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="course not found",
        ) from None

    summary = await compute_cohort_summary(
        db,
        course_id=course.id,
        course_slug=course.slug,
        course_title=course.title,
    )
    return AdminCohortSummaryOut(
        course_slug=summary.course_slug,
        course_title=summary.course_title,
        enrolled_count=summary.enrolled_count,
        average_score=summary.average_score,
        completion_rate=summary.completion_rate,
        stuck_learners=[
            StuckLearnerOut.model_validate(s) for s in summary.stuck_learners
        ],
        tag_heatmap=[
            TagHeatmapEntryOut.model_validate(t) for t in summary.tag_heatmap
        ],
    )
