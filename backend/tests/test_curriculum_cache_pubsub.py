"""Sprint 9 LOW-2 — curriculum cache pub/sub tests."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services import curriculum_cache_pubsub as pubsub


@pytest.mark.asyncio
async def test_notify_cache_reload_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "app.services.curriculum_cache_pubsub.settings.curriculum_cache_pubsub_enabled",
        False,
    )
    with patch("app.services.curriculum_cache_pubsub.Redis") as redis_cls:
        await pubsub.notify_cache_reload("ai-driven-dev")
        redis_cls.from_url.assert_not_called()


@pytest.mark.asyncio
async def test_notify_cache_reload_publishes_slug(monkeypatch):
    monkeypatch.setattr(
        "app.services.curriculum_cache_pubsub.settings.curriculum_cache_pubsub_enabled",
        True,
    )
    monkeypatch.setattr(
        "app.services.curriculum_cache_pubsub.settings.curriculum_cache_invalidate_channel",
        "test-channel",
    )
    client = AsyncMock()
    client.publish = AsyncMock()
    client.aclose = AsyncMock()
    with patch(
        "app.services.curriculum_cache_pubsub.Redis.from_url",
        return_value=client,
    ):
        await pubsub.notify_cache_reload("ai-era-se")
    client.publish.assert_awaited_once_with("test-channel", "ai-era-se")
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_cache_reload_swallows_redis_errors(monkeypatch):
    monkeypatch.setattr(
        "app.services.curriculum_cache_pubsub.settings.curriculum_cache_pubsub_enabled",
        True,
    )
    client = AsyncMock()
    client.publish = AsyncMock(side_effect=ConnectionError("redis down"))
    client.aclose = AsyncMock()
    with patch(
        "app.services.curriculum_cache_pubsub.Redis.from_url",
        return_value=client,
    ):
        await pubsub.notify_cache_reload("ai-driven-dev")
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_invalidation_reloads_single_course(
    db_session, seed_curriculum,
):
    from app.data.courses import runtime
    from app.models.curriculum_phase import CurriculumPhase
    from app.models.course import Course
    from sqlalchemy import select, update

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    before = runtime.get_cached_course("ai-driven-dev").phases[0].title

    dev_id = (
        await db_session.execute(
            select(Course.id).where(Course.slug == "ai-driven-dev")
        )
    ).scalar_one()
    await db_session.execute(
        update(CurriculumPhase)
        .where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        )
        .values(title="PubSub 更新")
    )
    await db_session.commit()

    await pubsub.apply_invalidation("ai-driven-dev")
    after = runtime.get_cached_course("ai-driven-dev").phases[0].title
    assert before != after
    assert after == "PubSub 更新"


@pytest.mark.asyncio
async def test_apply_invalidation_full_reload(db_session, seed_curriculum):
    from app.data.courses import runtime

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    assert runtime.get_cached_course("ai-era-se").slug == "ai-era-se"

    await pubsub.apply_invalidation("*")
    assert runtime.get_cached_course("ai-driven-dev").slug == "ai-driven-dev"
