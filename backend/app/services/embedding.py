"""Embedding write helpers."""

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding_client import EmbeddingClient
from app.models.embedding import Embedding


async def upsert_embeddings(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    user_id: uuid.UUID | None,
    course_id: uuid.UUID,
    items: list[tuple[str, str, int | None, str]],
) -> None:
    """Embed a batch of texts and insert into embeddings table.

    items: list of (source_type, source_ref, phase, content) tuples.

    For a given (source_type, source_ref), any pre-existing rows are
    deleted before insertion (idempotent re-embedding).

    Sprint 7: ``course_id`` is required (NOT NULL on the embeddings
    table). All embeddings tag the course they belong to so RAG search
    can scope retrieval per course.
    """
    if not items:
        return

    for source_type, source_ref, _, _ in items:
        await db.execute(
            delete(Embedding).where(
                Embedding.source_type == source_type,
                Embedding.source_ref == source_ref,
            )
        )

    contents = [c for _, _, _, c in items]
    vectors = await client.embed(contents)

    for (source_type, source_ref, phase, content), vec in zip(items, vectors, strict=True):
        db.add(
            Embedding(
                user_id=user_id,
                course_id=course_id,
                source_type=source_type,
                source_ref=source_ref,
                phase=phase,
                content=content,
                embedding=vec,
            )
        )
    await db.flush()
