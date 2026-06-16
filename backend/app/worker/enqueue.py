"""Enqueue grading jobs (arq) or run inline when async is disabled."""

from __future__ import annotations

import uuid

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings
from app.worker.curriculum_embeddings_job import run_curriculum_embeddings_job
from app.worker.grading_job import run_grading_job

_pool: ArqRedis | None = None


async def init_grading_pool() -> None:
    """Create a shared arq Redis pool (FastAPI lifespan)."""
    global _pool
    if not settings.grading_async_enabled:
        return
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))


async def close_grading_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def enqueue_grading(submission_id: uuid.UUID) -> None:
    """Dispatch grading. Inline when async is off (tests / fallback)."""
    if not settings.grading_async_enabled:
        await run_grading_job({}, str(submission_id))
        return
    if _pool is None:
        raise RuntimeError("grading pool not initialised — call init_grading_pool()")
    await _pool.enqueue_job("run_grading_job", str(submission_id))


async def enqueue_curriculum_embeddings(
    course_slug: str,
    source_refs: list[str],
) -> None:
    """Dispatch publish-time embedding refresh. Inline when async is off."""
    if not source_refs:
        return
    if not settings.grading_async_enabled:
        await run_curriculum_embeddings_job({}, course_slug, source_refs)
        return
    if _pool is None:
        raise RuntimeError("grading pool not initialised — call init_grading_pool()")
    await _pool.enqueue_job(
        "run_curriculum_embeddings_job",
        course_slug,
        source_refs,
    )
