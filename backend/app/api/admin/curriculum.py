"""Sprint 9 — admin curriculum editing API (`/api/admin/curriculum/...`)."""

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.data.courses import CourseNotFoundError
from app.db.session import get_db
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.models.user import User
from app.schemas.admin_curriculum import (
    AdminCurriculumCourseDetail,
    AdminCurriculumCourseList,
    AdminCurriculumCourseSummary,
    AdminCurriculumPublishOut,
    AdminPhaseEditOut,
    AdminPhaseUpdateRequest,
    AdminTaskEditOut,
    AdminTaskUpdateRequest,
)
from app.services.curriculum_edit import (
    PhaseNotFoundError,
    TaskNotFoundError,
    count_pending_drafts,
    discard_drafts,
    publish_course,
    put_phase_draft,
    put_task_draft,
)

router = APIRouter(prefix="/api/admin/curriculum", tags=["admin"])


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


@router.get("/", response_model=AdminCurriculumCourseList)
async def list_courses(
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


@router.get("/{course_slug}", response_model=AdminCurriculumCourseDetail)
async def get_detail(
    course_slug: str = Path(...),
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


@router.put(
    "/{course_slug}/phases/{phase_no}",
    response_model=AdminPhaseEditOut,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def put_phase(
    request: Request,
    payload: AdminPhaseUpdateRequest,
    course_slug: str = Path(...),
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
    course_slug: str = Path(...),
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
    "/{course_slug}/publish",
    response_model=AdminCurriculumPublishOut,
)
@limiter.limit(lambda: settings.admin_curriculum_publish_rate_limit)
async def publish(
    request: Request,
    course_slug: str = Path(...),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCurriculumPublishOut:
    try:
        result = await publish_course(db, course_slug=course_slug)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    await db.commit()
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
    course_slug: str = Path(...),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await discard_drafts(db, course_slug=course_slug)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    await db.commit()
    return None
