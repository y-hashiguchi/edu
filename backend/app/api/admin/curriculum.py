"""Sprint 9 — admin curriculum editing API (`/api/admin/curriculum/...`)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.data.courses import CourseNotFoundError, runtime
from app.db.session import get_db
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.models.user import User
from app.schemas.admin_curriculum import (
    AdminCourseCreateOut,
    AdminCourseCreateRequest,
    AdminCurriculumCourseDetail,
    AdminCurriculumCourseList,
    AdminCurriculumCourseSummary,
    AdminCurriculumPublishOut,
    AdminPhaseEditOut,
    AdminPhaseUpdateRequest,
    AdminTaskEditOut,
    AdminTaskMoveRequest,
    AdminTaskUpdateRequest,
)
from app.services.curriculum_course import (
    CourseHasEnrollmentsError,
    CourseHasSubmissionsError,
    CourseNotFoundError as AdminCourseNotFoundError,
    CourseSlugExistsError,
    CourseSlugInvalidError,
    ProtectedCourseError,
    add_course,
    delete_course,
)
from app.services.curriculum_edit import (
    CannotDeleteLastTaskError,
    InvalidTaskMoveError,
    PhaseNotFoundError,
    TaskHasSubmissionsError,
    TaskNotFoundError,
    add_task,
    count_pending_drafts,
    delete_task,
    discard_drafts,
    move_task,
    publish_course,
    put_phase_draft,
    put_task_draft,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/curriculum", tags=["admin"])

# Sprint 9 follow-up LOW-1: course_slug の fast-fail regex。a-z / 0-9 /
# `_` / `-` の最大 80 文字。production の slug (`ai-driven-dev`,
# `ai-era-se`) は両方このパターンを満たす。
_SLUG_PATTERN = r"^[a-z0-9_-]{1,80}$"


def _task_to_dto(t: CurriculumTask) -> AdminTaskEditOut:
    return AdminTaskEditOut(
        task_no=t.task_no,
        title=t.title,
        description=t.description,
        skill_tags=list(t.skill_tags or []),
        deliverable=t.deliverable,
        week_label=t.week_label,
        draft_title=t.draft_title,
        draft_description=t.draft_description,
        draft_skill_tags=t.draft_skill_tags,
        draft_deliverable=t.draft_deliverable,
        draft_week_label=t.draft_week_label,
        updated_at=t.updated_at,
    )


def _phase_to_dto(
    p: CurriculumPhase, tasks: list[CurriculumTask]
) -> AdminPhaseEditOut:
    return AdminPhaseEditOut(
        phase_no=p.phase_no,
        title=p.title,
        goal=p.goal,
        system_prompt=p.system_prompt,
        draft_title=p.draft_title,
        draft_goal=p.draft_goal,
        draft_system_prompt=p.draft_system_prompt,
        tasks=[_task_to_dto(t) for t in sorted(tasks, key=lambda r: r.task_no)],
        updated_at=p.updated_at,
    )


async def _reload_course_cache(db: AsyncSession, course_slug: str) -> None:
    """Structure change 後に runtime cache を更新する。"""
    await runtime.reload_course(db, course_slug)
    from app.services.curriculum_cache_pubsub import notify_cache_reload

    await notify_cache_reload(course_slug)


async def _evict_course_cache(course_slug: str) -> None:
    """course 削除後に runtime cache から除去する。"""
    runtime.evict_course(course_slug)
    from app.services.curriculum_cache_pubsub import notify_cache_reload

    await notify_cache_reload(f"-{course_slug}")


@router.get("/", response_model=AdminCurriculumCourseList)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def list_courses(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCurriculumCourseList:
    rows = (
        await db.execute(select(Course).order_by(Course.sort_order))
    ).scalars().all()
    items: list[AdminCurriculumCourseSummary] = []
    for c in rows:
        n = await count_pending_drafts(db, course_slug=c.slug)
        items.append(
            AdminCurriculumCourseSummary(
                slug=c.slug, title=c.title, pending_draft_count=n
            )
        )
    return AdminCurriculumCourseList(items=items)


@router.post(
    "/courses",
    response_model=AdminCourseCreateOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def create_course(
    request: Request,
    payload: AdminCourseCreateRequest,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCourseCreateOut:
    try:
        result = await add_course(
            db,
            slug=payload.slug,
            title=payload.title,
            description=payload.description,
        )
    except CourseSlugInvalidError:
        raise HTTPException(status_code=422, detail="invalid course slug")
    except CourseSlugExistsError:
        raise HTTPException(status_code=409, detail="course slug already exists")
    await db.commit()
    await _reload_course_cache(db, result.slug)
    logger.info(
        "curriculum.create_course slug=%s by=%s",
        result.slug,
        _admin.email,
    )
    return AdminCourseCreateOut(
        slug=result.slug,
        title=result.title,
        description=result.description,
        sort_order=result.sort_order,
        phase_count=result.phase_count,
        created_at=result.created_at,
    )


@router.delete(
    "/courses/{course_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def remove_course(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_course(db, slug=course_slug)
    except AdminCourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except ProtectedCourseError:
        raise HTTPException(status_code=409, detail="protected course cannot be deleted")
    except CourseHasEnrollmentsError:
        raise HTTPException(
            status_code=409, detail="course has enrollments and cannot be deleted"
        )
    except CourseHasSubmissionsError:
        raise HTTPException(
            status_code=409, detail="course has submissions and cannot be deleted"
        )
    await db.commit()
    await _evict_course_cache(course_slug)
    logger.info(
        "curriculum.delete_course slug=%s by=%s",
        course_slug,
        _admin.email,
    )
    return None


@router.get("/{course_slug}", response_model=AdminCurriculumCourseDetail)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def get_detail(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCurriculumCourseDetail:
    course = (
        await db.execute(select(Course).where(Course.slug == course_slug))
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    phases = (await db.execute(
        select(CurriculumPhase)
        .where(CurriculumPhase.course_id == course.id)
        .order_by(CurriculumPhase.phase_no)
    )).scalars().all()
    phase_ids = [p.id for p in phases]
    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
    )).scalars().all() if phase_ids else []
    by_phase: dict = {pid: [] for pid in phase_ids}
    for t in tasks:
        by_phase[t.phase_id].append(t)

    return AdminCurriculumCourseDetail(
        slug=course.slug,
        title=course.title,
        phases=[_phase_to_dto(p, by_phase.get(p.id, [])) for p in phases],
    )


# Sprint 9 follow-up MED-5 — system_prompt threat model:
# `system_prompt` (max 8000 chars) は学習者全員の Claude prompt にそのまま
# 注入される privileged field。コンプロマイズされた admin アカウントから
# 学習者の chat 振る舞い改変・PII 漏洩誘導・grading 偏向が可能になる。
# 防御:
#   1. is_admin RBAC (本ルート)
#   2. write rate limit (120/min) は publish/discard と書き込み同居
#   3. publish 時の audit log (admin email を INFO 出力)
# 未実装の防御 (将来):
#   - system_prompt 専用の更に厳しい rate limit
#   - publish 時の二要素認証
#   - system_prompt 変更前後の diff を audit table に永続化
@router.put(
    "/{course_slug}/phases/{phase_no}",
    response_model=AdminPhaseEditOut,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def put_phase(
    request: Request,
    payload: AdminPhaseUpdateRequest,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    phase_no: int = Path(ge=1),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminPhaseEditOut:
    try:
        row = await put_phase_draft(
            db,
            course_slug=course_slug,
            phase_no=phase_no,
            payload=payload.model_dump(exclude_unset=True),
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail="phase not found")
    await db.commit()
    await db.refresh(row)

    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id == row.id)
    )).scalars().all()
    return _phase_to_dto(row, list(tasks))


@router.put(
    "/{course_slug}/phases/{phase_no}/tasks/{task_no}",
    response_model=AdminTaskEditOut,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def put_task(
    request: Request,
    payload: AdminTaskUpdateRequest,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    phase_no: int = Path(ge=1),
    task_no: int = Path(ge=1),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTaskEditOut:
    body = payload.model_dump(exclude_unset=True)
    if "skill_tags" in body and body["skill_tags"] is not None:
        body["skill_tags"] = payload.normalized_skill_tags()
    try:
        row = await put_task_draft(
            db,
            course_slug=course_slug,
            phase_no=phase_no,
            task_no=task_no,
            payload=body,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail="phase not found")
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="task not found")
    await db.commit()
    await db.refresh(row)
    return _task_to_dto(row)


@router.post(
    "/{course_slug}/phases/{phase_no}/tasks",
    response_model=AdminTaskEditOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def post_task(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    phase_no: int = Path(ge=1),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTaskEditOut:
    try:
        row = await add_task(db, course_slug=course_slug, phase_no=phase_no)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail="phase not found")
    await db.commit()
    await _reload_course_cache(db, course_slug)
    await db.refresh(row)
    logger.info(
        "curriculum.add_task slug=%s phase=%d task_no=%d by=%s",
        course_slug,
        phase_no,
        row.task_no,
        _admin.email,
    )
    return _task_to_dto(row)


@router.delete(
    "/{course_slug}/phases/{phase_no}/tasks/{task_no}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def remove_task(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    phase_no: int = Path(ge=1),
    task_no: int = Path(ge=1),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_task(
            db,
            course_slug=course_slug,
            phase_no=phase_no,
            task_no=task_no,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail="phase not found")
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="task not found")
    except CannotDeleteLastTaskError:
        raise HTTPException(
            status_code=409, detail="cannot delete the last task in phase"
        )
    except TaskHasSubmissionsError:
        raise HTTPException(
            status_code=409, detail="task has submissions and cannot be deleted"
        )
    await db.commit()
    await _reload_course_cache(db, course_slug)
    logger.info(
        "curriculum.delete_task slug=%s phase=%d task_no=%d by=%s",
        course_slug,
        phase_no,
        task_no,
        _admin.email,
    )
    return None


@router.post(
    "/{course_slug}/phases/{phase_no}/tasks/{task_no}/move",
    response_model=AdminPhaseEditOut,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def reorder_task(
    request: Request,
    payload: AdminTaskMoveRequest,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    phase_no: int = Path(ge=1),
    task_no: int = Path(ge=1),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminPhaseEditOut:
    try:
        row = await move_task(
            db,
            course_slug=course_slug,
            phase_no=phase_no,
            task_no=task_no,
            to_task_no=payload.to_task_no,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail="phase not found")
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="task not found")
    except InvalidTaskMoveError:
        raise HTTPException(status_code=422, detail="invalid task move")
    await db.commit()
    await _reload_course_cache(db, course_slug)
    await db.refresh(row)
    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id == row.id)
    )).scalars().all()
    logger.info(
        "curriculum.move_task slug=%s phase=%d task_no=%d to=%d by=%s",
        course_slug,
        phase_no,
        task_no,
        payload.to_task_no,
        _admin.email,
    )
    return _phase_to_dto(row, list(tasks))


@router.post(
    "/{course_slug}/publish",
    response_model=AdminCurriculumPublishOut,
)
@limiter.limit(lambda: settings.admin_curriculum_publish_rate_limit)
async def publish(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCurriculumPublishOut:
    try:
        result = await publish_course(db, course_slug=course_slug)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    await db.commit()
    await _reload_course_cache(db, course_slug)
    # Sprint 9 review HIGH (security-reviewer): publish is irreversible and
    # affects every learner in the course. Log who triggered it.
    logger.info(
        "curriculum.publish slug=%s phases=%d tasks=%d by=%s",
        result.slug,
        result.published_phase_count,
        result.published_task_count,
        _admin.email,
    )
    return AdminCurriculumPublishOut(
        slug=result.slug,
        published_phase_count=result.published_phase_count,
        published_task_count=result.published_task_count,
        published_at=result.published_at,
    )


@router.post(
    "/{course_slug}/draft",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def discard(
    request: Request,
    course_slug: str = Path(..., pattern=_SLUG_PATTERN),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await discard_drafts(db, course_slug=course_slug)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    await db.commit()
    logger.info(
        "curriculum.discard slug=%s by=%s",
        course_slug,
        _admin.email,
    )
    return None
