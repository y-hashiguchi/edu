from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claude_client import ClaudeClient, get_claude_client
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionOut
from app.services.progress import is_phase_unlocked
from app.services.submission import (
    SubmissionPhaseInvalidError,
    SubmissionTaskInvalidError,
    list_user_submissions,
    upsert_and_grade,
)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    claude: ClaudeClient = Depends(get_claude_client),
    db: AsyncSession = Depends(get_db),
) -> SubmissionOut:
    if not await is_phase_unlocked(db, current_user.id, payload.phase):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"phase {payload.phase} is locked",
        )
    try:
        row = await upsert_and_grade(
            db=db,
            claude=claude,
            user_id=current_user.id,
            phase=payload.phase,
            task_no=payload.task_no,
            content=payload.content,
            uploads=[],
        )
    except SubmissionPhaseInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"phase {e.args[0]} not found",
        ) from e
    except SubmissionTaskInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"task {e.args[0]} not found",
        ) from e

    return SubmissionOut.model_validate(row)


@router.get("/{phase}", response_model=list[SubmissionOut])
async def list_my_submissions(
    phase: int = Path(ge=1, le=4),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionOut]:
    if not await is_phase_unlocked(db, current_user.id, phase):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"phase {phase} is locked"
        )
    rows = await list_user_submissions(db, current_user.id, phase)
    return [SubmissionOut.model_validate(r) for r in rows]
