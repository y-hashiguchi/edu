"""arq job — re-embed curriculum tasks after admin publish (Sprint 20)."""

from __future__ import annotations

import logging

from app.core.embedding_client import EmbeddingClient
from app.data.courses import runtime
from app.db.session import SessionLocal
from app.services.curriculum_embeddings import seed_course_embeddings_refs

logger = logging.getLogger(__name__)


async def run_curriculum_embeddings_job(
    _ctx: dict,
    course_slug: str,
    source_refs: list[str],
) -> None:
    if not source_refs:
        return
    client = EmbeddingClient()
    async with SessionLocal() as db:
        await runtime.reload_course(db, course_slug)
        count = await seed_course_embeddings_refs(
            db, course_slug, source_refs, client=client
        )
        await db.commit()
    logger.info(
        "curriculum embeddings job slug=%s refs=%d embedded=%d",
        course_slug,
        len(source_refs),
        count,
    )


async def run_curriculum_embeddings_full_job(
    _ctx: dict,
    course_slug: str,
) -> None:
    from app.services.curriculum_embeddings import seed_course_embeddings

    client = EmbeddingClient()
    async with SessionLocal() as db:
        await runtime.reload_course(db, course_slug)
        count = await seed_course_embeddings(db, course_slug, client=client)
        await db.commit()
    logger.info(
        "curriculum embeddings full job slug=%s embedded=%d",
        course_slug,
        count,
    )
