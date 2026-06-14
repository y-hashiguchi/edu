"""Sprint 10 — course-scoped cohort aggregation for admin dashboard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.courses import get_course
from app.models.enrollment import Enrollment
from app.models.grading_attempt import GradingAttempt
from app.models.progress import Progress, ProgressStatus
from app.models.submission import Submission
from app.models.user import User
from app.services.weakness import MIN_TAG_SUBMISSIONS


@dataclass(frozen=True)
class StuckLearner:
    user_id: uuid.UUID
    display_name: str
    email_masked: str
    last_activity_at: datetime | None
    current_phase: int
    submission_count: int
    reason: str  # "no_submissions" | "inactive_7d"


@dataclass(frozen=True)
class TagHeatmapEntry:
    tag: str
    average_score: float
    submission_count: int


@dataclass(frozen=True)
class CohortSummary:
    course_slug: str
    course_title: str
    enrolled_count: int
    average_score: float | None
    completion_rate: float
    stuck_learners: list[StuckLearner]
    tag_heatmap: list[TagHeatmapEntry]


def _mask_email(email: str) -> str:
    local, sep, domain = email.partition("@")
    if not sep:
        return "***"
    return f"{local[:2]}***@{domain}"


def _task_skill_tags(course_slug: str, phase: int, task_no: int) -> list[str]:
    for p in get_course(course_slug).phases:
        if p.phase == phase:
            for t in p.tasks:
                if t.task_no == task_no:
                    return list(t.skill_tags)
    return []


def _current_phase(
    progress_rows: list[tuple[int, str]],
    total_phases: int,
) -> int:
    by_phase = {phase: status for phase, status in progress_rows}
    for phase in range(total_phases, 0, -1):
        status = by_phase.get(phase, ProgressStatus.LOCKED.value)
        if status in (
            ProgressStatus.IN_PROGRESS.value,
            ProgressStatus.SUBMITTED.value,
        ):
            return phase
    for phase in range(1, total_phases + 1):
        status = by_phase.get(phase, ProgressStatus.LOCKED.value)
        if status != ProgressStatus.COMPLETED.value:
            return phase
    return total_phases


def _is_course_complete(
    progress_rows: list[tuple[int, str]],
    total_phases: int,
) -> bool:
    by_phase = {phase: status for phase, status in progress_rows}
    return all(
        by_phase.get(phase, ProgressStatus.LOCKED.value)
        == ProgressStatus.COMPLETED.value
        for phase in range(1, total_phases + 1)
    )


async def compute_cohort_summary(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    course_slug: str,
    course_title: str,
    stuck_inactive_days: int | None = None,
    now: datetime | None = None,
) -> CohortSummary:
    """Aggregate cohort metrics for active enrollments in one course."""
    inactive_days = (
        stuck_inactive_days
        if stuck_inactive_days is not None
        else settings.cohort_stuck_inactive_days
    )
    as_of = now or datetime.now(UTC)
    cutoff = as_of - timedelta(days=inactive_days)

    course_data = get_course(course_slug)
    total_phases = len(course_data.phases)

    enroll_stmt = (
        select(
            Enrollment.user_id,
            Enrollment.enrolled_at,
            User.name,
            User.email,
        )
        .join(User, User.id == Enrollment.user_id)
        .where(
            Enrollment.course_id == course_id,
            Enrollment.status == "active",
        )
    )
    enroll_rows = (await db.execute(enroll_stmt)).all()
    enrolled_count = len(enroll_rows)

    if enrolled_count == 0:
        return CohortSummary(
            course_slug=course_slug,
            course_title=course_title,
            enrolled_count=0,
            average_score=None,
            completion_rate=0.0,
            stuck_learners=[],
            tag_heatmap=[],
        )

    user_ids = [r[0] for r in enroll_rows]

    sub_stats_stmt = (
        select(
            Submission.user_id,
            func.count(Submission.id),
            func.max(Submission.submitted_at),
            func.max(Submission.graded_at),
        )
        .where(
            Submission.course_id == course_id,
            Submission.user_id.in_(user_ids),
        )
        .group_by(Submission.user_id)
    )
    sub_stats = {
        r[0]: (int(r[1]), r[2], r[3])
        for r in (await db.execute(sub_stats_stmt)).all()
    }

    latest_attempt_subq = (
        select(
            Submission.user_id,
            GradingAttempt.score,
            Submission.graded_at,
            Submission.submitted_at,
        )
        .join(GradingAttempt, GradingAttempt.submission_id == Submission.id)
        .where(
            Submission.course_id == course_id,
            Submission.user_id.in_(user_ids),
            GradingAttempt.status == "graded",
            GradingAttempt.score.is_not(None),
        )
        .order_by(Submission.id, GradingAttempt.created_at.desc())
        .distinct(Submission.id)
        .subquery()
    )
    latest_score_stmt = (
        select(latest_attempt_subq.c.user_id, latest_attempt_subq.c.score)
        .order_by(
            latest_attempt_subq.c.user_id,
            func.coalesce(
                latest_attempt_subq.c.graded_at,
                latest_attempt_subq.c.submitted_at,
            ).desc(),
        )
        .distinct(latest_attempt_subq.c.user_id)
    )
    latest_scores = [
        float(r[1]) for r in (await db.execute(latest_score_stmt)).all()
    ]
    average_score = (
        round(mean(latest_scores), 2) if latest_scores else None
    )

    progress_stmt = select(
        Progress.user_id,
        Progress.phase,
        Progress.status,
    ).where(
        Progress.course_id == course_id,
        Progress.user_id.in_(user_ids),
    )
    progress_by_user: dict[uuid.UUID, list[tuple[int, str]]] = {
        uid: [] for uid in user_ids
    }
    for uid, phase, status in (await db.execute(progress_stmt)).all():
        progress_by_user[uid].append((phase, status))

    completion_rates = []
    for uid in user_ids:
        rows = progress_by_user.get(uid, [])
        completed = sum(
            1 for _, st in rows if st == ProgressStatus.COMPLETED.value
        )
        completion_rates.append(completed / total_phases)
    completion_rate = round(mean(completion_rates), 4)

    stuck_learners: list[StuckLearner] = []
    for user_id, enrolled_at, name, email in enroll_rows:
        count, last_submitted, last_graded = sub_stats.get(
            user_id, (0, None, None)
        )
        last_activity = last_graded or last_submitted or enrolled_at
        progress_rows = progress_by_user.get(user_id, [])
        current_phase = _current_phase(progress_rows, total_phases)
        course_complete = _is_course_complete(progress_rows, total_phases)

        reason: str | None = None
        if count == 0 and enrolled_at < cutoff:
            reason = "no_submissions"
        elif (
            count > 0
            and not course_complete
            and last_activity < cutoff
        ):
            reason = "inactive_7d"

        if reason is not None:
            stuck_learners.append(
                StuckLearner(
                    user_id=user_id,
                    display_name=name,
                    email_masked=_mask_email(email),
                    last_activity_at=last_activity,
                    current_phase=current_phase,
                    submission_count=count,
                    reason=reason,
                )
            )

    stuck_learners.sort(
        key=lambda s: (s.last_activity_at or datetime.min.replace(tzinfo=UTC))
    )

    tag_stmt = (
        select(
            Submission.phase,
            Submission.task_no,
            GradingAttempt.score,
        )
        .join(GradingAttempt, GradingAttempt.submission_id == Submission.id)
        .where(
            Submission.course_id == course_id,
            Submission.user_id.in_(user_ids),
            GradingAttempt.status == "graded",
            GradingAttempt.score.is_not(None),
        )
        .order_by(Submission.id, GradingAttempt.created_at.desc())
        .distinct(Submission.id)
    )
    tag_scores: dict[str, list[float]] = {}
    for phase, task_no, score in (await db.execute(tag_stmt)).all():
        for tag in _task_skill_tags(course_slug, phase, task_no):
            tag_scores.setdefault(tag, []).append(float(score))

    tag_heatmap = [
        TagHeatmapEntry(
            tag=tag,
            average_score=round(mean(scores), 2),
            submission_count=len(scores),
        )
        for tag, scores in tag_scores.items()
        if len(scores) >= MIN_TAG_SUBMISSIONS
    ]
    tag_heatmap.sort(key=lambda e: (e.average_score, e.tag))

    return CohortSummary(
        course_slug=course_slug,
        course_title=course_title,
        enrolled_count=enrolled_count,
        average_score=average_score,
        completion_rate=completion_rate,
        stuck_learners=stuck_learners,
        tag_heatmap=tag_heatmap,
    )
