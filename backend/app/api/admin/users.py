"""Admin → users list + detail (Sprint 4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
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
