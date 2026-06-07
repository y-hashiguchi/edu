"""Notification DTOs (Sprint 4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    recipient_user_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    # `link` is optional and free-form (frontend resolves it as a
    # router path). Validation here is length only — the frontend
    # decides at click time whether to follow it.
    link: str | None = Field(default=None, max_length=500)


class NotificationOut(BaseModel):
    """A single notification with the sender's display name denormalised
    so the client never needs a second request to render."""

    id: uuid.UUID
    recipient_user_id: uuid.UUID
    sender_user_id: uuid.UUID
    sender_name: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationListOut(BaseModel):
    """`items` is capped at `settings.notification_poll_limit` so each
    30 s poll stays cheap. `unread_count` is the true total of unread
    rows — clients use it to render the bell badge accurately even
    when the inbox is deeper than the list cap."""

    items: list[NotificationOut]
    unread_count: int
