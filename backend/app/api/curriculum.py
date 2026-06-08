from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.data.curriculum import CURRICULUM
from app.db.session import get_db
from app.models.progress import ProgressStatus
from app.models.user import User
from app.schemas.curriculum import PhaseSummary
from app.services.progress import list_progress

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.get("/phases", response_model=list[PhaseSummary])
async def list_phases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PhaseSummary]:
    rows = await list_progress(db, current_user.id)
    status_by_phase = {r.phase: r.status for r in rows}

    return [
        PhaseSummary(
            phase=phase_no,
            title=phase["title"],
            goal=phase["goal"],
            duration=phase["duration"],
            skills=phase["skills"],
            tasks=[item["title"] for item in phase["tasks"]],
            locked=(
                status_by_phase.get(phase_no, ProgressStatus.LOCKED.value)
                == ProgressStatus.LOCKED.value
            ),
            status=status_by_phase.get(phase_no, ProgressStatus.LOCKED.value),
        )
        for phase_no, phase in sorted(CURRICULUM.items())
    ]
