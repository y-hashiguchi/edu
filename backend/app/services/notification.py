"""Notification domain service (Sprint 4)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import Notification
from app.models.user import User


class RecipientNotFoundError(Exception):
    """Admin tried to send to a user that does not exist. We catch this
    pre-flight rather than relying on the FK violation so the API can
    give a clear 404 instead of a 500 + DB error."""


class NotificationNotFoundError(Exception):
    """Either the notification doesn't exist, or it exists but is not
    addressed to the requesting user. Mapped to 404 in both cases so an
    intruder cannot distinguish ownership from a status code."""


class RecipientInboxFullError(Exception):
    """HIGH-2 (sprint-4 security review): a recipient cannot accumulate
    more than `settings.notification_unread_cap` unread rows. Caps DB
    growth and bounds the recurring COUNT(*) cost on each 30 s poll.
    Routers map this to 429 with a Retry-After header so callers know
    the right human action is "wait for the learner to read"."""

    def __init__(self, recipient_id: str, cap: int) -> None:
        super().__init__(
            f"recipient {recipient_id} inbox at unread cap ({cap})"
        )
        self.cap = cap


async def send(
    *,
    db: AsyncSession,
    sender_id: uuid.UUID,
    recipient_id: uuid.UUID,
    title: str,
    body: str,
    link: str | None,
) -> Notification:
    recipient = (
        await db.execute(select(User).where(User.id == recipient_id))
    ).scalar_one_or_none()
    if recipient is None:
        raise RecipientNotFoundError(str(recipient_id))

    # HIGH-2: refuse to write past the per-recipient unread cap. The
    # cap is enforced at write time (not via DB constraint) so the
    # error can be returned with a meaningful 429 instead of an opaque
    # IntegrityError.
    unread = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_user_id == recipient_id,
                Notification.read_at.is_(None),
            )
        )
    ).scalar_one()
    if unread >= settings.notification_unread_cap:
        raise RecipientInboxFullError(
            str(recipient_id), settings.notification_unread_cap
        )

    note = Notification(
        recipient_user_id=recipient_id,
        sender_user_id=sender_id,
        title=title,
        body=body,
        link=link,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def list_for_recipient(
    db: AsyncSession,
    *,
    recipient_id: uuid.UUID,
    limit: int,
) -> tuple[list[tuple[Notification, User]], int]:
    """The inbox slice + an accurate total-unread count.

    The slice is capped at `limit` (newest first) so polling cost stays
    bounded. The unread count is the unbounded scalar so the bell badge
    is accurate even when the inbox is deeper than the list."""

    rows = (
        await db.execute(
            select(Notification, User)
            .join(User, Notification.sender_user_id == User.id)
            .where(Notification.recipient_user_id == recipient_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    ).all()

    unread = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_user_id == recipient_id,
                Notification.read_at.is_(None),
            )
        )
    ).scalar_one()
    return [(n, u) for n, u in rows], unread


async def list_sent_by(
    db: AsyncSession, sender_id: uuid.UUID
) -> list[Notification]:
    """The 'outbox' view for an admin — only notifications they
    themselves sent. Co-instructors get their own outboxes; this is the
    structural guarantee that an admin cannot accidentally see another
    instructor's inbox traffic."""
    return list(
        (
            await db.execute(
                select(Notification)
                .where(Notification.sender_user_id == sender_id)
                .order_by(Notification.created_at.desc())
            )
        ).scalars().all()
    )


async def mark_read(
    *,
    db: AsyncSession,
    notification_id: uuid.UUID,
    recipient_id: uuid.UUID,
) -> Notification:
    """Idempotent: re-marking an already-read notification is a no-op
    success. The 404 branch fires for missing rows AND rows that belong
    to another recipient (BOLA fence)."""
    note = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_user_id == recipient_id,
            )
        )
    ).scalar_one_or_none()
    if note is None:
        raise NotificationNotFoundError(str(notification_id))
    if note.read_at is None:
        note.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(note)
    return note
