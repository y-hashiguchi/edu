"""Sprint 5 progress summary — completion + average score aggregation.

Sprint 7: total_tasks is computed from the requested course's phase
definitions instead of the legacy default-course constant, so a learner
enrolled in `ai-era-se` sees their own course's denominator."""

import uuid
from dataclasses import dataclass
from statistics import mean

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses import get_course
from app.services.weakness import MIN_SUBMISSION_THRESHOLD, _latest_graded_scores


@dataclass(frozen=True)
class ProgressSummary:
    completed_tasks: int  # = submission_count (1 submission per task)
    total_tasks: int
    submission_count: int
    average_score: float | None  # None below MIN_SUBMISSION_THRESHOLD


async def compute_progress_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
) -> ProgressSummary:
    total_tasks = sum(len(p.tasks) for p in get_course(course_slug).phases)
    rows = await _latest_graded_scores(db, user_id, course_id)
    count = len(rows)
    if count < MIN_SUBMISSION_THRESHOLD:
        return ProgressSummary(
            completed_tasks=count, total_tasks=total_tasks,
            submission_count=count, average_score=None,
        )
    avg = round(mean(float(r[1]) for r in rows), 2)
    return ProgressSummary(
        completed_tasks=count, total_tasks=total_tasks,
        submission_count=count, average_score=avg,
    )
