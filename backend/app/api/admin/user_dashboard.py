"""GET /api/admin/users/{user_id}/dashboard — admin can view any
learner's Sprint 5 dashboard (sans nudge). Sprint 6."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.core.embedding_client import get_embedding_client
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    AdminDashboardResponse,
    ProgressSummaryOut,
    RecommendationOut,
    RecommendationsBlock,
    TagAverageOut,
    WeaknessOut,
)
from app.services.dashboard import compose_dashboard_for_admin

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


@router.get(
    "/{user_id}/dashboard",
    response_model=AdminDashboardResponse,
)
async def get_admin_user_dashboard(
    user_id: uuid.UUID,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    embedding_client=Depends(get_embedding_client),
) -> AdminDashboardResponse:
    exists = (
        await db.execute(select(User.id).where(User.id == user_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    data = await compose_dashboard_for_admin(
        db, embedding_client=embedding_client, user_id=user_id,
    )
    return AdminDashboardResponse(
        progress_summary=ProgressSummaryOut.model_validate(data.progress_summary),
        weakness=WeaknessOut(
            has_enough_data=data.weakness.has_enough_data,
            top_weaknesses=[
                TagAverageOut.model_validate(w)
                for w in data.weakness.top_weaknesses
            ],
        ),
        recommendations=RecommendationsBlock(
            items=[
                RecommendationOut.model_validate(r)
                for r in data.recommendations
            ],
        ),
    )
