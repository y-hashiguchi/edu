"""Sprint 7 course schemas (catalog + enrollment projections)."""

from datetime import datetime

from pydantic import BaseModel, Field


class CourseCatalogItem(BaseModel):
    slug: str
    title: str
    description: str | None
    sort_order: int


class CourseCatalogOut(BaseModel):
    items: list[CourseCatalogItem]


class EnrollmentOut(BaseModel):
    """Returned in admin user detail and as part of /api/courses."""

    course_slug: str
    course_title: str
    status: str = Field(pattern=r"^(active|paused|completed)$")
    enrolled_at: datetime


class MyCourseItem(BaseModel):
    """A course the authenticated learner is enrolled in."""

    slug: str
    title: str
    description: str | None
    status: str = Field(pattern=r"^(active|paused|completed)$")


class MyCoursesOut(BaseModel):
    items: list[MyCourseItem]
