"""Redis pub/sub to sync curriculum cache across uvicorn workers (Sprint 9 LOW-2).

When an admin publishes curriculum changes, the handling worker reloads
its process-local cache and broadcasts the course slug (or ``*`` for full
reload) so peer workers reload from DB without restart.
"""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_stop_event: asyncio.Event | None = None
_listener_task: asyncio.Task[None] | None = None
_redis: Redis | None = None


async def apply_invalidation(slug: str) -> None:
    """Reload cache for one course or all courses from the DB."""
    from app.data.courses import runtime
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        if slug == "*":
            await runtime.reload_from_db(db)
        else:
            await runtime.reload_course(db, slug)
    logger.info("curriculum cache reloaded from pub/sub slug=%r", slug)


async def notify_cache_reload(slug: str) -> None:
    """Publish invalidation after the publishing worker has reloaded locally."""
    if not settings.curriculum_cache_pubsub_enabled:
        return
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.publish(settings.curriculum_cache_invalidate_channel, slug)
    except Exception:
        # Best-effort: publish must succeed even when Redis is unavailable
        # (CI E2E, single-worker dev without Redis, transient outages).
        logger.warning(
            "curriculum cache pub/sub notify failed slug=%r",
            slug,
            exc_info=True,
        )
    finally:
        with asyncio.suppress(Exception):
            await client.aclose()


async def _listen_loop() -> None:
    global _redis
    assert _stop_event is not None
    _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = _redis.pubsub()
    await pubsub.subscribe(settings.curriculum_cache_invalidate_channel)
    logger.info(
        "curriculum cache pub/sub listener started channel=%s",
        settings.curriculum_cache_invalidate_channel,
    )
    try:
        while not _stop_event.is_set():
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if not message or message.get("type") != "message":
                continue
            slug = message.get("data")
            if not isinstance(slug, str) or not slug:
                continue
            try:
                await apply_invalidation(slug)
            except Exception:
                logger.exception(
                    "curriculum cache reload failed after pub/sub slug=%r",
                    slug,
                )
    finally:
        await pubsub.unsubscribe(settings.curriculum_cache_invalidate_channel)
        await pubsub.aclose()
        await _redis.aclose()
        _redis = None


async def start_listener() -> None:
    """Start background listener (no-op when disabled)."""
    global _stop_event, _listener_task
    if not settings.curriculum_cache_pubsub_enabled:
        return
    if _listener_task is not None and not _listener_task.done():
        return
    _stop_event = asyncio.Event()
    _listener_task = asyncio.create_task(_listen_loop())


async def stop_listener() -> None:
    """Stop background listener and close Redis connection."""
    global _stop_event, _listener_task
    if _listener_task is None:
        return
    if _stop_event is not None:
        _stop_event.set()
    try:
        await asyncio.wait_for(_listener_task, timeout=5.0)
    except asyncio.TimeoutError:
        _listener_task.cancel()
        with asyncio.suppress(asyncio.CancelledError):
            await _listener_task
    _listener_task = None
    _stop_event = None
