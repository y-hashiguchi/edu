"""Sprint 7 — public catalog + authenticated my-courses listing."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.course import (
    CourseCatalogItem,
    CourseCatalogOut,
    MyCourseItem,
    MyCoursesOut,
)
from app.services.enrollment import list_my_courses

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("/catalog", response_model=CourseCatalogOut)
async def get_catalog(db: AsyncSession = Depends(get_db)) -> CourseCatalogOut:
    """Public list of available courses (used by the registration form)."""
    result = await db.execute(
        select(Course).order_by(Course.sort_order, Course.title)
    )
    items = [
        CourseCatalogItem(
            slug=c.slug,
            title=c.title,
            description=c.description,
            sort_order=c.sort_order,
        )
        for c in result.scalars().all()
    ]
    return CourseCatalogOut(items=items)


@router.get("", response_model=MyCoursesOut)
async def get_my_courses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MyCoursesOut:
    """Authenticated learner's enrolled courses."""
    items = await list_my_courses(db, user_id=user.id)
    return MyCoursesOut(
        items=[
            MyCourseItem(
                slug=it.slug, title=it.title,
                description=it.description, status=it.status,
            )
            for it in items
        ]
    )
