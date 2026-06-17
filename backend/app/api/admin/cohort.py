"""Sprint 10 — admin cohort summary API."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.admin_cohort import (
    AdminCohortLabelsOut,
    AdminCohortSummaryOut,
    StuckLearnerOut,
    TagHeatmapEntryOut,
)
from app.services.cohort_csv import render_cohort_csv
from app.services.cohort_summary import compute_cohort_summary
from app.services.enrollment import (
    CourseNotFoundError,
    _get_course_by_slug,
    list_cohort_labels,
)

router = APIRouter(prefix="/api/admin/courses", tags=["admin"])

_SLUG_PATTERN = r"^[a-z0-9_-]{1,80}$"
_COHORT_LABEL_PATTERN = r"^[a-zA-Z0-9._-]{1,80}$"


async def _course_or_404(db: AsyncSession, course_slug: str) -> Course:
    try:
        return await _get_course_by_slug(db, course_slug)
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="course not found",
        ) from None


def _summary_out(summary) -> AdminCohortSummaryOut:
    return AdminCohortSummaryOut(
        course_slug=summary.course_slug,
        course_title=summary.course_title,
        enrolled_count=summary.enrolled_count,
        average_score=summary.average_score,
        completion_rate=summary.completion_rate,
        stuck_learners=[StuckLearnerOut.model_validate(s) for s in summary.stuck_learners],
        tag_heatmap=[TagHeatmapEntryOut.model_validate(t) for t in summary.tag_heatmap],
        cohort_label=summary.cohort_label,
    )


@router.get(
    "/{course_slug}/cohort-labels",
    response_model=AdminCohortLabelsOut,
)
@limiter.limit(lambda: settings.admin_cohort_rate_limit)
async def get_cohort_labels(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCohortLabelsOut:
    course = await _course_or_404(db, course_slug)
    labels = await list_cohort_labels(db, course_id=course.id)
    return AdminCohortLabelsOut(items=labels)


@router.get(
    "/{course_slug}/cohort-summary",
    response_model=AdminCohortSummaryOut,
)
@limiter.limit(lambda: settings.admin_cohort_rate_limit)
async def get_cohort_summary(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    cohort_label: str | None = Query(default=None, pattern=_COHORT_LABEL_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCohortSummaryOut:
    course = await _course_or_404(db, course_slug)
    summary = await compute_cohort_summary(
        db,
        course_id=course.id,
        course_slug=course.slug,
        course_title=course.title,
        cohort_label=cohort_label,
    )
    return _summary_out(summary)


@router.get(
    "/{course_slug}/cohort-summary/export",
    response_class=Response,
)
@limiter.limit(lambda: settings.admin_cohort_rate_limit)
async def export_cohort_summary_csv(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    cohort_label: str | None = Query(default=None, pattern=_COHORT_LABEL_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    course = await _course_or_404(db, course_slug)
    summary = await compute_cohort_summary(
        db,
        course_id=course.id,
        course_slug=course.slug,
        course_title=course.title,
        cohort_label=cohort_label,
    )
    csv_body = render_cohort_csv(summary)
    suffix = f"-{cohort_label}" if cohort_label else ""
    filename = f"cohort-{course.slug}{suffix}.csv"
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
