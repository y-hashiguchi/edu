"""Sprint 5 progress summary — completion + average score aggregation."""

import uuid
from dataclasses import dataclass
from statistics import mean

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import iter_all_phase_task_pairs
from app.services.weakness import MIN_SUBMISSION_THRESHOLD, _latest_graded_scores


TOTAL_TASKS = sum(1 for _ in iter_all_phase_task_pairs())
"""Total curriculum tasks. Computed once at module load so a future
curriculum expansion is picked up without code changes here."""


@dataclass(frozen=True)
class ProgressSummary:
    completed_tasks: int  # = submission_count (1 submission per task)
    total_tasks: int
    submission_count: int
    average_score: float | None  # None below MIN_SUBMISSION_THRESHOLD


async def compute_progress_summary(
    db: AsyncSession, user_id: uuid.UUID,
) -> ProgressSummary:
    rows = await _latest_graded_scores(db, user_id)
    count = len(rows)
    if count < MIN_SUBMISSION_THRESHOLD:
        return ProgressSummary(
            completed_tasks=count, total_tasks=TOTAL_TASKS,
            submission_count=count, average_score=None,
        )
    avg = round(mean(float(r[1]) for r in rows), 2)
    return ProgressSummary(
        completed_tasks=count, total_tasks=TOTAL_TASKS,
        submission_count=count, average_score=avg,
    )
