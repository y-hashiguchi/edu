"""Sprint 5 dashboard orchestrator.

Calls four sub-services and never lets a sub-service exception take down
the whole response — the dashboard is a multi-section UX, so each
section degrades to its empty form rather than 500-ing the page."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.nudge import (
    LLM_FAILURE_FALLBACK, NudgeResult, get_or_generate,
)
from app.services.progress_summary import (
    ProgressSummary, compute_progress_summary,
)
from app.services.recommendation import Recommendation, compute_recommendations
from app.services.weakness import WeaknessResult, compute_weakness


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardData:
    progress_summary: ProgressSummary
    weakness: WeaknessResult
    recommendations: list[Recommendation]
    nudge: NudgeResult


async def compose_dashboard(
    db: AsyncSession,
    *,
    claude,
    embedding_client,
    user_id: uuid.UUID,
) -> DashboardData:
    # progress_summary and weakness share an underlying query
    # (_latest_graded_scores) but we don't pre-cache it here — the cost
    # is one extra round-trip in exchange for not having to plumb the
    # cache through 4 service interfaces. Revisit if dashboard p99
    # latency becomes a complaint.
    try:
        progress = await compute_progress_summary(db, user_id)
    except Exception:
        logger.exception("progress_summary failed")
        progress = ProgressSummary(
            completed_tasks=0, total_tasks=12,
            submission_count=0, average_score=None,
        )

    try:
        weakness = await compute_weakness(db, user_id)
    except Exception:
        logger.exception("weakness failed")
        weakness = WeaknessResult(has_enough_data=False, top_weaknesses=[])

    top_tags = [w.tag for w in weakness.top_weaknesses]
    try:
        recs = await compute_recommendations(
            db, embedding_client,
            user_id=user_id, top_weakness_tags=top_tags,
        )
    except Exception:
        logger.exception("recommendations failed")
        recs = []

    top_rec_key = f"{recs[0].phase}:{recs[0].task_no}" if recs else None
    progress_text = (
        f"完了: {progress.completed_tasks}/{progress.total_tasks} タスク"
        + (
            f"、平均スコア: {progress.average_score}"
            if progress.average_score is not None else ""
        )
    )
    rec_titles = [r.title for r in recs]

    try:
        nudge = await get_or_generate(
            db, claude=claude, user_id=user_id,
            weakness_tags=top_tags,
            top_recommendation_key=top_rec_key,
            submission_count=progress.submission_count,
            recommendation_titles=rec_titles,
            progress_text=progress_text,
        )
    except Exception:
        logger.exception("nudge failed at orchestrator level")
        nudge = NudgeResult(
            body=LLM_FAILURE_FALLBACK,
            generated_at=datetime.now(UTC),
            is_fresh=False,
        )

    return DashboardData(
        progress_summary=progress, weakness=weakness,
        recommendations=recs, nudge=nudge,
    )


@dataclass(frozen=True)
class AdminDashboardData:
    """Sprint 6: admin が任意の受講者の dashboard を見るときのデータ形。
    Sprint 5 の DashboardData から nudge を除外したもの。AI 一言は
    受講者プライベートなので admin には surface しない。"""

    progress_summary: ProgressSummary
    weakness: WeaknessResult
    recommendations: list[Recommendation]


async def compose_dashboard_for_admin(
    db: AsyncSession,
    *,
    embedding_client,
    user_id: uuid.UUID,
) -> AdminDashboardData:
    """Admin-facing dashboard composer (Sprint 6).

    Mirrors `compose_dashboard` but never calls the nudge service —
    the AI one-liner is private feedback to the learner, not
    surveillance material for the instructor. Each sub-service still
    degrades to its empty form on failure so a single sub-service
    exception does not 500 the entire admin dashboard."""
    try:
        progress = await compute_progress_summary(db, user_id)
    except Exception:
        logger.exception("progress_summary failed (admin)")
        progress = ProgressSummary(
            completed_tasks=0, total_tasks=12,
            submission_count=0, average_score=None,
        )

    try:
        weakness = await compute_weakness(db, user_id)
    except Exception:
        logger.exception("weakness failed (admin)")
        weakness = WeaknessResult(has_enough_data=False, top_weaknesses=[])

    top_tags = [w.tag for w in weakness.top_weaknesses]
    try:
        recs = await compute_recommendations(
            db, embedding_client,
            user_id=user_id, top_weakness_tags=top_tags,
        )
    except Exception:
        logger.exception("recommendations failed (admin)")
        recs = []

    return AdminDashboardData(
        progress_summary=progress, weakness=weakness, recommendations=recs,
    )
