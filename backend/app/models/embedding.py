"""Embedding ORM model (pgvector-backed)."""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 output dim
EMBEDDING_DIM = 384


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index(
            "ix_embeddings_course_user_phase",
            "course_id", "user_id", "phase",
        ),
        Index(
            "ix_embeddings_vector_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # NULL means "global / curriculum" content shared across users
    # within a course. course_id stays NOT NULL — global-to-the-
    # platform content (none today) would need a separate solution.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50))
    source_ref: Mapped[str] = mapped_column(String(200))
    phase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
