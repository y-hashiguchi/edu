"""Instructor comment domain service (Sprint 4)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instructor_comment import InstructorComment
from app.models.submission import Submission
from app.models.user import User


class SubmissionNotFoundError(Exception):
    """Either the submission row does not exist, or it exists but is not
    owned by the requesting user. Routers map this to 404 in both cases
    — never 403 — so an attacker cannot tell the two apart from a
    response status alone (BOLA-distinguishability)."""


async def create_comment(
    *,
    db: AsyncSession,
    submission_id: uuid.UUID,
    author_user_id: uuid.UUID,
    body: str,
) -> InstructorComment:
    sub = (
        await db.execute(
            select(Submission).where(Submission.id == submission_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        raise SubmissionNotFoundError(str(submission_id))

    comment = InstructorComment(
        submission_id=submission_id,
        author_user_id=author_user_id,
        body=body,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def list_for_admin(
    db: AsyncSession, submission_id: uuid.UUID
) -> list[tuple[InstructorComment, User]]:
    """Admin-facing read: all comments joined with their author User.

    Does NOT verify the submission exists — the admin landing pages already
    deal with empty arrays, and the caller (router) returns the same shape
    either way. An admin who hits an unknown UUID gets `[]`, which matches
    the dashboard's expectation when filtering."""
    rows = (
        await db.execute(
            select(InstructorComment, User)
            .join(User, InstructorComment.author_user_id == User.id)
            .where(InstructorComment.submission_id == submission_id)
            .order_by(InstructorComment.created_at.asc())
        )
    ).all()
    return [(c, u) for c, u in rows]


async def list_for_owner(
    db: AsyncSession,
    *,
    submission_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> list[tuple[InstructorComment, User]]:
    """Learner-facing read: same shape as list_for_admin, but only if the
    submission belongs to `owner_user_id`. Raises SubmissionNotFoundError
    when ownership fails so the router can return a uniform 404."""
    sub = (
        await db.execute(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.user_id == owner_user_id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise SubmissionNotFoundError(str(submission_id))
    return await list_for_admin(db, submission_id)
