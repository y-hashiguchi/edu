"""Sprint 7 — course registry.

Public API:
  COURSE_REGISTRY: dict[slug, CourseData]
  DEFAULT_COURSE_SLUG: 'ai-driven-dev'
  get_course(slug) -> CourseData
  get_phases(slug) -> tuple[PhaseData, ...]
  get_phase(slug, phase_no) -> PhaseData
  CourseNotFoundError / PhaseNotFoundError
"""

from app.data.courses.ai_driven_dev import AI_DRIVEN_DEV_COURSE
# from app.data.courses.ai_era_se import AI_ERA_SE_COURSE  # Task 3 で有効化
from app.data.courses.types import CourseData, PhaseData, TaskItem


class CourseNotFoundError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course slug {slug!r} not found")
        self.slug = slug


class PhaseNotFoundError(Exception):
    def __init__(self, slug: str, phase: int) -> None:
        super().__init__(f"phase {phase} not found in course {slug!r}")
        self.slug = slug
        self.phase = phase


DEFAULT_COURSE_SLUG: str = "ai-driven-dev"

COURSE_REGISTRY: dict[str, CourseData] = {
    AI_DRIVEN_DEV_COURSE.slug: AI_DRIVEN_DEV_COURSE,
    # AI_ERA_SE_COURSE.slug: AI_ERA_SE_COURSE,  # Task 3 で有効化
}


def get_course(slug: str) -> CourseData:
    try:
        return COURSE_REGISTRY[slug]
    except KeyError:
        raise CourseNotFoundError(slug) from None


def get_phases(slug: str) -> tuple[PhaseData, ...]:
    return get_course(slug).phases


def get_phase(slug: str, phase_no: int) -> PhaseData:
    for p in get_course(slug).phases:
        if p.phase == phase_no:
            return p
    raise PhaseNotFoundError(slug, phase_no)


__all__ = [
    "COURSE_REGISTRY",
    "CourseData",
    "CourseNotFoundError",
    "DEFAULT_COURSE_SLUG",
    "PhaseData",
    "PhaseNotFoundError",
    "TaskItem",
    "get_course",
    "get_phase",
    "get_phases",
]
