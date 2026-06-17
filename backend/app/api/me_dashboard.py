"""GET /api/me/dashboard — single-fetch learner dashboard (Sprint 5).

Sprint 7: scoped via CourseContext so the dashboard reflects only the
selected course (?course=…) — enrollment is enforced by get_course_context."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.claude_client import get_nudge_claude_client
from app.core.course_deps import CourseContext, get_course_context
from app.core.deps import get_current_user
from app.core.embedding_client import get_embedding_client
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardResponse,
    NudgeOut,
    ProgressSummaryOut,
    RecommendationOut,
    RecommendationsBlock,
    TagAverageOut,
    WeaknessOut,
)
from app.services.dashboard import compose_dashboard

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/dashboard", response_model=DashboardResponse)
@limiter.limit(lambda: settings.me_write_rate_limit)
async def get_my_dashboard(
    request: Request,  # required by slowapi key_func=get_remote_address
    ctx: CourseContext = Depends(get_course_context),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    claude=Depends(get_nudge_claude_client),
    embedding_client=Depends(get_embedding_client),
) -> DashboardResponse:
    data = await compose_dashboard(
        db,
        claude=claude,
        embedding_client=embedding_client,
        user_id=user.id,
        course_id=ctx.course.id,
        course_slug=ctx.course.slug,
    )
    return DashboardResponse(
        progress_summary=ProgressSummaryOut.model_validate(data.progress_summary),
        weakness=WeaknessOut(
            has_enough_data=data.weakness.has_enough_data,
            top_weaknesses=[TagAverageOut.model_validate(w) for w in data.weakness.top_weaknesses],
        ),
        recommendations=RecommendationsBlock(
            items=[RecommendationOut.model_validate(r) for r in data.recommendations],
        ),
        nudge=NudgeOut(
            body=data.nudge.body,
            generated_at=data.nudge.generated_at,
            is_fresh=data.nudge.is_fresh,
        ),
    )
