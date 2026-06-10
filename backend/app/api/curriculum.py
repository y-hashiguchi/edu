from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.course_deps import CourseContext, get_course_context
from app.core.deps import get_current_user
from app.data.courses import DEFAULT_COURSE_SLUG
from app.db.session import get_db
from app.models.progress import ProgressStatus
from app.models.user import User
from app.schemas.curriculum import PhaseSummary
from app.services.progress import list_progress

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


# Legacy Sprint 0 metadata for the default (ai-driven-dev) course only.
# These fields don't exist on PhaseData (Sprint 7 dataclass), so we keep
# them inline here to preserve the original /api/curriculum/phases shape.
_LEGACY_DURATION: dict[int, str] = {
    1: "2〜3週間",
    2: "3〜4週間",
    3: "AI補助コーディング期間",
    4: "4〜6週間",
}

_LEGACY_SKILLS: dict[int, list[str]] = {
    1: [
        "Git / GitHub",
        "VSCode拡張機能",
        "ターミナル操作",
        "REST API基礎",
    ],
    2: [
        "プロンプトエンジニアリング",
        "Cursor IDE",
        "GitHub Copilot",
        "Claude活用",
    ],
    3: [
        "AIペアプログラミング",
        "AIによるコードレビュー",
        "テスト自動生成",
        "仕様書からのコード生成",
    ],
    4: [
        "API連携（Claude / OpenAI）",
        "RAG基礎",
        "PythonでAIツール作成",
        "プロダクト設計",
    ],
}


@router.get("/phases", response_model=list[PhaseSummary])
async def list_phases(
    current_user: User = Depends(get_current_user),
    ctx: CourseContext = Depends(get_course_context),
    db: AsyncSession = Depends(get_db),
) -> list[PhaseSummary]:
    rows = await list_progress(db, current_user.id)
    # Filter progress to current course (service still returns all-course rows
    # for backward compat — narrow here):
    status_by_phase = {
        r.phase: r.status for r in rows if r.course_id == ctx.course.id
    }

    is_default_course = ctx.course.slug == DEFAULT_COURSE_SLUG
    duration_map = _LEGACY_DURATION if is_default_course else {}
    skills_map = _LEGACY_SKILLS if is_default_course else {}

    return [
        PhaseSummary(
            phase=p.phase,
            title=p.title,
            goal=p.goal,
            duration=duration_map.get(p.phase, ""),
            skills=list(skills_map.get(p.phase, [])),
            tasks=[t.title for t in p.tasks],
            locked=(
                status_by_phase.get(p.phase, ProgressStatus.LOCKED.value)
                == ProgressStatus.LOCKED.value
            ),
            status=status_by_phase.get(p.phase, ProgressStatus.LOCKED.value),
        )
        for p in ctx.course.phases
    ]
