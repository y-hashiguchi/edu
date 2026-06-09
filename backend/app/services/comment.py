"""Instructor comment domain service (Sprint 4)."""

import uuid

from sqlalchemy import select, text
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

    MED-3 (sprint-4 security follow-up): verify the submission exists
    and raise SubmissionNotFoundError otherwise. BOLA risk is zero
    (admins read everything), but returning `[]` for an unknown UUID
    broke status-code symmetry with POST and with the submission
    detail endpoint — refactors and front-end error handling rely on
    that symmetry."""
    sub_id = (
        await db.execute(
            select(Submission.id).where(Submission.id == submission_id)
        )
    ).scalar_one_or_none()
    if sub_id is None:
        raise SubmissionNotFoundError(str(submission_id))
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


class InvalidParentError(Exception):
    """parent_id が同じ submission に属さない場合に投げる。Router は 400 にマップ。"""


class UnauthorizedThreadError(Exception):
    """先祖を辿って admin author に辿り着けないスレッドへの返信。Router は 403 にマップ。"""


async def _ancestor_has_admin(db: AsyncSession, comment_id: uuid.UUID) -> bool:
    """WITH RECURSIVE で先祖を辿り、author_user_id に is_admin=True の
    User が存在するか判定する。1 クエリで完結。"""
    stmt = text("""
        WITH RECURSIVE ancestors AS (
            SELECT id, parent_id, author_user_id
            FROM instructor_comments WHERE id = :start
            UNION ALL
            SELECT c.id, c.parent_id, c.author_user_id
            FROM instructor_comments c
            JOIN ancestors a ON c.id = a.parent_id
        )
        SELECT 1 FROM ancestors a
        JOIN users u ON u.id = a.author_user_id
        WHERE u.is_admin = TRUE LIMIT 1
    """)
    result = await db.execute(stmt, {"start": comment_id})
    return result.first() is not None


async def _thread_admin_authors(
    db: AsyncSession, parent_comment_id: uuid.UUID,
) -> set[uuid.UUID]:
    """同じスレッドに参加している admin author 全員の id を返す (重複なし)."""
    stmt = text("""
        WITH RECURSIVE ancestors AS (
            SELECT id, parent_id, author_user_id
            FROM instructor_comments WHERE id = :start
            UNION ALL
            SELECT c.id, c.parent_id, c.author_user_id
            FROM instructor_comments c
            JOIN ancestors a ON c.id = a.parent_id
        )
        SELECT DISTINCT a.author_user_id FROM ancestors a
        JOIN users u ON u.id = a.author_user_id
        WHERE u.is_admin = TRUE
    """)
    rows = (await db.execute(stmt, {"start": parent_comment_id})).all()
    return {r.author_user_id for r in rows}


async def post_reply(
    *,
    db: AsyncSession,
    submission_id: uuid.UUID,
    learner_user_id: uuid.UUID,
    parent_id: uuid.UUID,
    body: str,
) -> InstructorComment:
    """受講者から admin スレッドへの返信投稿。
    バリデーション順:
      1. parent が同じ submission に属するか (InvalidParentError → 400)
      2. submission の所有者が学習者本人か (SubmissionNotFoundError → 404)
      3. 先祖に admin author が居るか (UnauthorizedThreadError → 403)
    """
    # 1. 親 comment と submission 一致確認
    parent = (
        await db.execute(
            select(InstructorComment).where(InstructorComment.id == parent_id)
        )
    ).scalar_one_or_none()
    if parent is None or parent.submission_id != submission_id:
        raise InvalidParentError(str(parent_id))

    # 2. submission 所有者確認 (BOLA fence)
    sub = (
        await db.execute(
            select(Submission).where(Submission.id == submission_id)
        )
    ).scalar_one_or_none()
    if sub is None or sub.user_id != learner_user_id:
        raise SubmissionNotFoundError(str(submission_id))

    # 3. 先祖 admin 確認
    if not await _ancestor_has_admin(db, parent_id):
        raise UnauthorizedThreadError(str(parent_id))

    # 4. comment 作成
    reply = InstructorComment(
        submission_id=submission_id,
        author_user_id=learner_user_id,
        parent_id=parent_id,
        body=body,
    )
    db.add(reply)
    await db.flush()

    # 5. Sprint 6: スレッド参加 admin 全員宛に Notification をファンアウト
    from app.models.notification import Notification
    admin_ids = await _thread_admin_authors(db, parent_id)
    for admin_id in admin_ids:
        db.add(Notification(
            recipient_user_id=admin_id,
            sender_user_id=learner_user_id,
            title="返信が届きました",
            body=body[:120],
            link=f"/admin/submissions/{submission_id}",
        ))
    await db.flush()
    return reply
