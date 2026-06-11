"""Read-only aggregations driving the admin dashboard.

Kept separate from `app.services.submission` etc. so the read-side
queries don't accidentally inherit any business rules from the
write-side services. Pure reads, no side effects.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.enrollment import Enrollment
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


async def resolve_primary_courses(
    db: AsyncSession,
    user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, uuid.UUID]:
    """Pick each user's "primary" course for the admin dashboard.

    Defined as the active enrollment with the smallest `Course.sort_order`
    (ties broken by `Course.id` via the natural SQL order, which is stable
    enough for an admin dashboard). Users with no active enrollment are
    omitted from the result — the caller decides whether to show empty
    counts / `None` weakness tag for them.

    Sprint 7: introduced so admin aggregates (weakness tag, phase counts)
    can be scoped to a single course instead of summing across every
    course the user has ever touched.
    """
    if not user_ids:
        return {}
    rows = (await db.execute(
        select(Enrollment.user_id, Enrollment.course_id, Course.sort_order)
        .join(Course, Enrollment.course_id == Course.id)
        .where(
            Enrollment.user_id.in_(user_ids),
            Enrollment.status == "active",
        )
        .order_by(Enrollment.user_id, Course.sort_order, Course.id)
    )).all()
    primary: dict[uuid.UUID, uuid.UUID] = {}
    for uid, cid, _so in rows:
        primary.setdefault(uid, cid)
    return primary


async def list_users_with_progress(
    db: AsyncSession, *, limit: int, offset: int
) -> list[tuple[User, list[Progress], uuid.UUID | None]]:
    """Newest-first user page joined with their primary-course progress.

    Loads progress in a single follow-up query (N=1 per page, not N=1
    per user) so the dashboard scales linearly with page size, not with
    the user-count column. Returns rows in the page-stable order — the
    caller can build summary objects without re-sorting.

    Sprint 7: progress rows are filtered to each user's primary active
    course (see `resolve_primary_courses`) so `completed_phases` /
    `in_progress_phases` reflect a single course rather than summing
    across every course the learner has ever interacted with — keeping
    the column consistent with the course-scoped `top_weakness_tag`.
    Users with no active enrollment get an empty progress list and a
    `None` primary-course id (caller passes the id straight back into
    the weakness bulk query).
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
    primary = await resolve_primary_courses(db, user_ids)

    grouped: dict[uuid.UUID, list[Progress]] = {u.id: [] for u in users}
    course_ids = list({cid for cid in primary.values()})
    if primary and course_ids:
        progress_rows = (
            await db.execute(
                select(Progress).where(
                    Progress.user_id.in_(list(primary.keys())),
                    Progress.course_id.in_(course_ids),
                )
            )
        ).scalars().all()
        # Keep only rows that match each user's own primary course —
        # without this filter a user with primary=A would also collect
        # another user's primary=B progress.
        for p in progress_rows:
            if primary.get(p.user_id) == p.course_id:
                grouped[p.user_id].append(p)

    return [(u, grouped[u.id], primary.get(u.id)) for u in users]


async def get_user_detail(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[
    User, list[Progress], dict[int, int | None], list[tuple[Enrollment, Course]]
] | None:
    """Drill-down for one learner. Returns None if the user doesn't
    exist (caller maps to 404). `latest_scores` is keyed by phase number
    and represents the cached `submissions.score` — i.e. the latest
    graded score per (user, phase). Phases with no graded submission
    map to None so the frontend can render an empty cell.

    Sprint 7: also returns every enrollment (any status) paired with its
    Course row so the router can build `AdminUserDetail.enrollments`
    without a second round-trip. Ordered by `Course.sort_order` so the
    admin UI's course selector is stable."""

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

    enrollment_rows = (
        await db.execute(
            select(Enrollment, Course)
            .join(Course, Enrollment.course_id == Course.id)
            .where(Enrollment.user_id == user_id)
            .order_by(Course.sort_order, Course.id)
        )
    ).all()
    enrollments: list[tuple[Enrollment, Course]] = [
        (e, c) for e, c in enrollment_rows
    ]

    return user, list(progress), latest_scores, enrollments


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
    "Course",
    list[SubmissionFile],
    list[GradingAttempt],
    list[tuple[InstructorComment, User]],
] | None:
    """Pull every piece the admin detail view needs in five queries.

    Returns None when the submission row doesn't exist (router maps to
    404). Comments are returned paired with the author User so the
    DTO can include `author_name` without a per-comment lookup.

    Sprint 7 MED-3: the submission's Course is also returned so the
    admin DTO can carry ``course_slug`` (used by the file-download URL).
    """
    from app.models.course import Course

    pair = (
        await db.execute(
            select(Submission, User, Course)
            .join(User, Submission.user_id == User.id)
            .join(Course, Submission.course_id == Course.id)
            .where(Submission.id == submission_id)
        )
    ).first()
    if pair is None:
        return None
    submission, learner, course = pair

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

    return submission, learner, course, list(files), list(history), comments
