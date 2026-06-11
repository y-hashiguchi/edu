from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.course_deps import CourseContext, get_course_context
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.progress import ProgressCompleteResponse, ProgressOut
from app.services.progress import (
    PhaseLockedError,
    PhaseNotFoundError,
    complete_phase,
    list_progress,
)

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=list[ProgressOut])
async def list_my_progress(
    current_user: User = Depends(get_current_user),
    ctx: CourseContext = Depends(get_course_context),
    db: AsyncSession = Depends(get_db),
) -> list[ProgressOut]:
    # Sprint 7 MED-1: scope at the service layer instead of post-filtering.
    rows = await list_progress(db, current_user.id, course_id=ctx.course.id)
    return [ProgressOut.model_validate(r) for r in rows]


@router.post("/{phase}/complete", response_model=ProgressCompleteResponse)
async def complete(
    phase: int = Path(ge=1, le=4),
    current_user: User = Depends(get_current_user),
    ctx: CourseContext = Depends(get_course_context),
    db: AsyncSession = Depends(get_db),
) -> ProgressCompleteResponse:
    # Sprint 7 MED-1: pass course_id + course_slug so next-phase unlock
    # uses the course registry and the Progress lookup is course-scoped.
    try:
        current, next_unlocked = await complete_phase(
            db,
            current_user.id,
            phase,
            course_id=ctx.course.id,
            course_slug=ctx.course.slug,
        )
    except PhaseLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"phase {e.phase} is locked"
        ) from e
    except PhaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"progress for phase {e.phase} not found",
        ) from e

    return ProgressCompleteResponse(
        phase=current.phase,
        status=current.status,
        started_at=current.started_at,
        completed_at=current.completed_at,
        next_unlocked=(
            ProgressOut.model_validate(next_unlocked) if next_unlocked else None
        ),
    )
