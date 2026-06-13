"""Sprint 7 — course registry. Sprint 9 — runtime cache rewire.

Public API:
  COURSE_REGISTRY: dict[slug, CourseData]   — legacy alias for the cache
  DEFAULT_COURSE_SLUG: 'ai-driven-dev'
  get_course(slug) -> CourseData             — cache 経由
  get_phases(slug) -> tuple[PhaseData, ...]
  get_phase(slug, phase_no) -> PhaseData
  CourseNotFoundError / PhaseNotFoundError

Sprint 9 後の挙動:
- `get_course()` は in-memory cache (`runtime._CACHE`) を読む。
- cache は app 起動時に `runtime.reload_from_db(db)` が満たす。
- 編集 → publish のサイクルは `runtime.reload_course(db, slug)` で 1 course
  分の cache だけを差し替える。
- 既存 `ai_driven_dev.py` / `ai_era_se.py` は Alembic seed のドキュメント
  および test fallback 用に残す。本番 runtime は読まない。
"""

from app.data.courses.ai_driven_dev import AI_DRIVEN_DEV_COURSE
from app.data.courses.ai_era_se import AI_ERA_SE_COURSE
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


# `COURSE_REGISTRY` is a backward-compatible alias kept for tests that
# still iterate over the python-side seed dict. Sprint 9 runtime code
# reads from `runtime._CACHE` via `get_course()`; this dict is NOT a
# source of truth at runtime.
COURSE_REGISTRY: dict[str, CourseData] = {
    AI_DRIVEN_DEV_COURSE.slug: AI_DRIVEN_DEV_COURSE,
    AI_ERA_SE_COURSE.slug: AI_ERA_SE_COURSE,
}


def get_course(slug: str) -> CourseData:
    """Cache-first lookup. Sprint 9 routes/services hit this via the cache.

    Test convenience: if the cache is empty (no `reload_from_db` was
    called — common for pure-unit tests that don't go through lifespan),
    fall back to `COURSE_REGISTRY`. Integration tests that exercise edit
    semantics must call `runtime.reload_from_db(db)` explicitly so they
    see the DB state, not the python literal.
    """
    from app.data.courses import runtime

    if runtime._CACHE:
        return runtime.get_cached_course(slug)
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
