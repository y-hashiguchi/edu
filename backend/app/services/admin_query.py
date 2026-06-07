"""Read-only aggregations driving the admin dashboard.

Kept separate from `app.services.submission` etc. so the read-side
queries don't accidentally inherit any business rules from the
write-side services. Pure reads, no side effects.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_attempt import GradingAttempt
from app.models.instructor_comment import InstructorComment
from app.models.progress import Progress
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.user import User


async def count_users(db: AsyncSession) -> int:
    return (
        await db.execute(select(func.count()).select_from(User))
    ).scalar_one()


async def list_users_with_progress(
    db: AsyncSession, *, limit: int, offset: int
) -> list[tuple[User, list[Progress]]]:
    """Newest-first user page joined with their progress rows.

    Loads progress in a single follow-up query (N=1 per page, not N=1
    per user) so the dashboard scales linearly with page size, not with
    the user-count column. Returns rows in the page-stable order — the
    caller can build summary objects without re-sorting.
    """
    users = (
        await db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    if not users:
        return []

    user_ids = [u.id for u in users]
    progress_rows = (
        await db.execute(
            select(Progress).where(Progress.user_id.in_(user_ids))
        )
    ).scalars().all()

    grouped: dict[uuid.UUID, list[Progress]] = {u.id: [] for u in users}
    for p in progress_rows:
        grouped[p.user_id].append(p)
    return [(u, grouped[u.id]) for u in users]


async def get_user_detail(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[User, list[Progress], dict[int, int | None]] | None:
    """Drill-down for one learner. Returns None if the user doesn't
    exist (caller maps to 404). `latest_scores` is keyed by phase number
    and represents the cached `submissions.score` — i.e. the latest
    graded score per (user, phase). Phases with no graded submission
    map to None so the frontend can render an empty cell."""

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        return None

    progress = (
        await db.execute(
            select(Progress)
            .where(Progress.user_id == user_id)
            .order_by(Progress.phase)
        )
    ).scalars().all()

    submissions = (
        await db.execute(
            select(Submission).where(Submission.user_id == user_id)
        )
    ).scalars().all()

    latest_scores: dict[int, int | None] = {phase: None for phase in range(1, 5)}
    for s in submissions:
        if s.score is None:
            continue
        current = latest_scores.get(s.phase)
        if current is None or s.score > current:
            latest_scores[s.phase] = s.score

    return user, list(progress), latest_scores


async def count_submissions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    phase: int | None,
) -> int:
    stmt = select(func.count()).select_from(Submission)
    if user_id is not None:
        stmt = stmt.where(Submission.user_id == user_id)
    if phase is not None:
        stmt = stmt.where(Submission.phase == phase)
    return (await db.execute(stmt)).scalar_one()


async def list_submissions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    phase: int | None,
    limit: int,
    offset: int,
) -> list[tuple[Submission, User]]:
    """Joined Submission + User rows newest-first.

    Returns paired ORM instances rather than a custom shape so the
    router can format the response with whatever DTO it likes without
    re-querying the user."""
    stmt = (
        select(Submission, User)
        .join(User, Submission.user_id == User.id)
    )
    if user_id is not None:
        stmt = stmt.where(Submission.user_id == user_id)
    if phase is not None:
        stmt = stmt.where(Submission.phase == phase)
    stmt = stmt.order_by(Submission.submitted_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()
    return [(sub, user) for sub, user in rows]


async def get_submission_detail(
    db: AsyncSession, submission_id: uuid.UUID
) -> tuple[
    Submission,
    User,
    list[SubmissionFile],
    list[GradingAttempt],
    list[tuple[InstructorComment, User]],
] | None:
    """Pull every piece the admin detail view needs in five queries.

    Returns None when the submission row doesn't exist (router maps to
    404). Comments are returned paired with the author User so the
    DTO can include `author_name` without a per-comment lookup."""

    pair = (
        await db.execute(
            select(Submission, User)
            .join(User, Submission.user_id == User.id)
            .where(Submission.id == submission_id)
        )
    ).first()
    if pair is None:
        return None
    submission, learner = pair

    files = (
        await db.execute(
            select(SubmissionFile)
            .where(SubmissionFile.submission_id == submission_id)
            .order_by(SubmissionFile.created_at)
        )
    ).scalars().all()

    history = (
        await db.execute(
            select(GradingAttempt)
            .where(GradingAttempt.submission_id == submission_id)
            .order_by(GradingAttempt.created_at.desc())
        )
    ).scalars().all()

    comment_rows = (
        await db.execute(
            select(InstructorComment, User)
            .join(User, InstructorComment.author_user_id == User.id)
            .where(InstructorComment.submission_id == submission_id)
            .order_by(InstructorComment.created_at.asc())
        )
    ).all()
    comments = [(c, a) for c, a in comment_rows]

    return submission, learner, list(files), list(history), comments
