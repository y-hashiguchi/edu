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
    parent_id: uuid.UUID | None = None,
) -> InstructorComment:
    sub = (
        await db.execute(
            select(Submission).where(Submission.id == submission_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        raise SubmissionNotFoundError(str(submission_id))

    # Sprint 6: parent_id 指定時は同 submission に属するか検証
    if parent_id is not None:
        parent = (
            await db.execute(
                select(InstructorComment).where(InstructorComment.id == parent_id)
            )
        ).scalar_one_or_none()
        if parent is None or parent.submission_id != submission_id:
            raise InvalidParentError(str(parent_id))

    comment = InstructorComment(
        submission_id=submission_id,
        author_user_id=author_user_id,
        body=body,
        parent_id=parent_id,
    )
    db.add(comment)
    # Sprint 6 (HIGH-1, code-review): commit ownership moved to the
    # router. Keeping db.commit() here would race with future
    # side-effects (notifications, audit log, etc.) that the caller
    # may want to enlist in the same transaction — the comment would
    # commit but the side-effect rollback would leave a half-state.
    # Pattern now matches post_reply: service flushes, caller commits.
    await db.flush()
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


MAX_THREAD_DEPTH = 50
"""MED-1 (sprint-6 follow-up): WITH RECURSIVE の hard cap。FK CASCADE で
構造的サイクルは作れないが、DB 直操作で生まれたサイクルや悪意的に深い
スレッドを防御。50 は人間の対話として現実的な最大深度の余裕分。"""


async def _ancestor_has_admin(db: AsyncSession, comment_id: uuid.UUID) -> bool:
    """WITH RECURSIVE で先祖を辿り、author_user_id に is_admin=True の
    User が存在するか判定する。1 クエリで完結。

    MED-1: depth カウンタで MAX_THREAD_DEPTH を超えたら停止。サイクルや
    悪意ある深いスレッドで CTE が無限再帰するのを防ぐ。"""
    stmt = text(f"""
        WITH RECURSIVE ancestors AS (
            SELECT id, parent_id, author_user_id, 1 AS depth
            FROM instructor_comments WHERE id = :start
            UNION ALL
            SELECT c.id, c.parent_id, c.author_user_id, a.depth + 1
            FROM instructor_comments c
            JOIN ancestors a ON c.id = a.parent_id
            WHERE a.depth < {MAX_THREAD_DEPTH}
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
    """同じスレッド (root から全 descendants) に参加している admin author
    全員の id を返す。

    HIGH-3 (sprint-6 follow-up): 以前は parent_id を辿る ancestor 走査だけ
    で、sibling 枝に居る admin (e.g. admin B が trunk に直接返信した状態)
    が学習者の通知ファンアウトから漏れていた。本実装は (1) 学習者が選んだ
    parent から root へ歩いて root を見つけ、(2) root から descendants を
    全方向に辿って参加 admin を全員集める 2 段階 CTE。

    MED-1: 両方向の走査に depth カウンタを入れ、MAX_THREAD_DEPTH 超過で
    停止。サイクルや悪意ある深いスレッドでの無限再帰を防ぐ。"""
    stmt = text(f"""
        WITH RECURSIVE ancestor_walk AS (
            SELECT id, parent_id, 1 AS depth
            FROM instructor_comments WHERE id = :start
            UNION ALL
            SELECT c.id, c.parent_id, aw.depth + 1
            FROM instructor_comments c
            JOIN ancestor_walk aw ON c.id = aw.parent_id
            WHERE aw.depth < {MAX_THREAD_DEPTH}
        ),
        root AS (
            SELECT id FROM ancestor_walk WHERE parent_id IS NULL LIMIT 1
        ),
        descendants AS (
            SELECT id, parent_id, author_user_id, 1 AS depth
            FROM instructor_comments
            WHERE id = (SELECT id FROM root)
            UNION ALL
            SELECT c.id, c.parent_id, c.author_user_id, d.depth + 1
            FROM instructor_comments c
            JOIN descendants d ON c.parent_id = d.id
            WHERE d.depth < {MAX_THREAD_DEPTH}
        )
        SELECT DISTINCT d.author_user_id FROM descendants d
        JOIN users u ON u.id = d.author_user_id
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

    # 5. Sprint 6: fan out via notification_service.send so the per-
    # recipient unread cap (settings.notification_unread_cap, default
    # 200) from Sprint 4 actually applies. Directly constructing
    # Notification rows here would bypass the cap and let a learner
    # with N admins in a thread emit N × me_write_rate_limit
    # admin-facing notifications per minute, defeating the Sprint 4
    # anti-flood defense (HIGH-1, sprint-6 security review).
    #
    # Note: notification_service.send() commits internally (one commit
    # per recipient). That is acceptable here — every successful send
    # IS persisted independently, and the reply row itself was already
    # flushed at step 4. RecipientInboxFullError / RecipientNotFoundError
    # are skipped so a single full inbox or a vanished admin does not
    # abort the whole fanout (or the reply itself); the caller's outer
    # commit in api/me.py then becomes a no-op for the reply if nothing
    # else changed.
    from app.services import notification as notification_service

    admin_ids = await _thread_admin_authors(db, parent_id)
    for admin_id in admin_ids:
        try:
            await notification_service.send(
                db=db,
                sender_id=learner_user_id,
                recipient_id=admin_id,
                title="返信が届きました",
                body=body[:120],
                link=f"/admin/submissions/{submission_id}",
            )
        except notification_service.RecipientInboxFullError:
            # Admin inbox at cap — skip silently. The reply itself
            # still succeeds; missing this one ping is preferable to
            # 500-ing the learner's POST.
            pass
        except notification_service.RecipientNotFoundError:
            # Race: admin row disappeared between the CTE lookup and
            # the send. Skip rather than abort.
            pass

    return reply
