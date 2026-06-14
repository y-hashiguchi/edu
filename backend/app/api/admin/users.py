"""Admin → users list + detail (Sprint 4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.data.courses import COURSE_REGISTRY, get_course
from app.db.session import get_db
from app.models.progress import ProgressStatus
from app.models.user import User
from app.schemas.admin import (
    AdminUserDetail,
    AdminUserListOut,
    AdminUserSummary,
)
from app.schemas.course import EnrollmentOut
from app.schemas.progress import ProgressOut
from app.services import admin_query
from app.services.enrollment import (
    AlreadyEnrolledError,
    CourseNotFoundError,
    _get_course_by_slug,
    enroll_user,
)
from app.services.progress import initialize_progress_for_course

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


@router.get("", response_model=AdminUserListOut)
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListOut:
    rows = await admin_query.list_users_with_progress(
        db, limit=limit, offset=offset
    )
    total = await admin_query.count_users(db)

    # Sprint 6: bulk 集計で N+1 回避
    # Sprint 7: weakness は (user_id, course_id) のペアで集計。primary course
    # が無い (active enrollment ゼロの) ユーザーは tag = None として残す。
    from app.services.weakness import compute_top_weakness_tags_bulk
    user_course_pairs = [
        (u.id, primary_course_id)
        for u, _progs, primary_course_id in rows
        if primary_course_id is not None
    ]
    top_tags = await compute_top_weakness_tags_bulk(db, user_course_pairs)

    items = [
        AdminUserSummary(
            id=u.id,
            email=u.email,
            name=u.name,
            created_at=u.created_at,
            is_admin=u.is_admin,
            completed_phases=sum(
                1 for p in progs if p.status == ProgressStatus.COMPLETED.value
            ),
            in_progress_phases=sum(
                1 for p in progs if p.status == ProgressStatus.IN_PROGRESS.value
            ),
            top_weakness_tag=top_tags.get(u.id),
        )
        for u, progs, _primary_course_id in rows
    ]
    return AdminUserListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=AdminUserDetail)
async def get_user(
    user_id: uuid.UUID,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    found = await admin_query.get_user_detail(db, user_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        )
    user, progress, latest_scores, enrollment_rows = found
    enrollments = [
        EnrollmentOut(
            course_slug=c.slug,
            course_title=c.title,
            status=e.status,
            enrolled_at=e.enrolled_at,
            cohort_label=e.cohort_label,
        )
        for e, c in enrollment_rows
    ]
    return AdminUserDetail(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        is_admin=user.is_admin,
        progress=[ProgressOut.model_validate(p) for p in progress],
        latest_scores=latest_scores,
        enrollments=enrollments,
    )


class AdminEnrollRequest(BaseModel):
    """Sprint 7 LOW-2 — admin-driven enroll payload."""

    course_slug: str = Field(min_length=1, max_length=64)
    cohort_label: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9._-]{1,80}$")


@router.post(
    "/{user_id}/enrollments",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def admin_enroll(
    user_id: uuid.UUID,
    payload: AdminEnrollRequest,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentOut:
    """Admin-driven enroll: add a course to an existing user.

    Sprint 7 LOW-2: previously the only way to enroll an existing user
    into a second course was direct SQL. This route reuses ``enroll_user``
    and seeds per-course progress so the learner can immediately start
    on the new course."""
    if payload.course_slug not in COURSE_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown course_slug: {payload.course_slug!r}",
        )

    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        )

    try:
        enr = await enroll_user(
            db,
            user_id=target.id,
            course_slug=payload.course_slug,
            cohort_label=payload.cohort_label,
        )
    except AlreadyEnrolledError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from e
    except CourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    course_data = get_course(payload.course_slug)
    db_course = await _get_course_by_slug(db, payload.course_slug)
    await initialize_progress_for_course(
        db,
        target.id,
        db_course.id,
        [p.phase for p in course_data.phases],
    )

    await db.commit()
    await db.refresh(enr)
    return EnrollmentOut(
        course_slug=db_course.slug,
        course_title=db_course.title,
        status=enr.status,
        enrolled_at=enr.enrolled_at,
        cohort_label=enr.cohort_label,
    )
