"""Sprint 5: AI nudge cache row.

Single row per user (PK = user_id). 24h TTL caching + an
input_signature lets us cheaply detect "the inputs that produced this
nudge have shifted" inside the window — when the learner submits a new
task or a weakness moves out of the top 3, the signature changes and
the dashboard regenerates even before the 24h timer expires.

LOW-5 (sprint-5 follow-up): no secondary index. The original schema
declared `ix_user_nudges_generated_at`, but no query in this app
filters or orders by `generated_at` — the cache lookup is by PK
user_id and the freshness check reads the row's own column. The
unused index was data-minimization friction (any read-only analytics
user with `pg_indexes` access could infer learner activity timing
from the index statistics). Dropped; reinstate via a new migration
when a real query consumer appears.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNudge(Base):
    __tablename__ = "user_nudges"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    input_signature: Mapped[str] = mapped_column(String(16), nullable=False)
