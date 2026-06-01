from fastapi import APIRouter

from app.data.curriculum import CURRICULUM
from app.schemas.curriculum import PhaseSummary

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.get("/phases", response_model=list[PhaseSummary])
def list_phases() -> list[PhaseSummary]:
    return [
        PhaseSummary(
            phase=phase_no,
            title=phase["title"],
            goal=phase["goal"],
            duration=phase["duration"],
            skills=phase["skills"],
            tasks=phase["tasks"],
        )
        for phase_no, phase in sorted(CURRICULUM.items())
    ]
