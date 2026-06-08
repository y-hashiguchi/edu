"""Sprint 5 AI nudge service.

Behavioural surface:
  - cache hit within TTL + same signature → reuse the row
  - cache miss / TTL expired / signature changed → regenerate via LLM
  - cold start (submission_count < threshold) → static text, no LLM
  - LLM exception with prior row → return stale, NOT overwriting cache
  - LLM exception with no prior row → static fallback, NOT persisting it
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.models.user_nudge import UserNudge
from app.services.nudge import (
    _build_signature, get_or_generate, COLD_START_BODY,
)


async def _make_user(db_session, email="n@e.com"):
    user = User(email=email, name="N", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _fake_claude(reply: str):
    """ClaudeClient.complete() returns a string; test double matches that."""
    client = MagicMock()
    client.complete = AsyncMock(return_value=reply)
    return client


@pytest.mark.asyncio
async def test_cold_start_returns_static_without_calling_llm(db_session):
    user = await _make_user(db_session)
    claude = _fake_claude("UNUSED")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=[], top_recommendation_key=None,
        submission_count=0,
    )
    assert out.body == COLD_START_BODY
    assert out.is_fresh is True
    claude.complete.assert_not_called()
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).first()
    assert row is None


@pytest.mark.asyncio
async def test_cache_miss_generates_and_persists(db_session):
    user = await _make_user(db_session)
    claude = _fake_claude("データ構造が伸びる Phase 2 タスク 1 をやろう。")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.is_fresh is True
    assert "Phase 2" in out.body
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).scalar_one()
    assert row.body == out.body
    assert len(row.input_signature) == 16


@pytest.mark.asyncio
async def test_cache_hit_within_ttl_does_not_call_llm(db_session):
    user = await _make_user(db_session)
    sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="cached body",
        generated_at=datetime.now(UTC), input_signature=sig,
    ))
    await db_session.commit()

    claude = _fake_claude("WOULD-BE-NEW")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "cached body"
    claude.complete.assert_not_called()


@pytest.mark.asyncio
async def test_signature_change_invalidates_cache_even_within_ttl(db_session):
    user = await _make_user(db_session)
    old_sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="stale", generated_at=datetime.now(UTC),
        input_signature=old_sig,
    ))
    await db_session.commit()

    claude = _fake_claude("regenerated body")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="3:2",  # changed
        submission_count=5,
    )
    assert out.body == "regenerated body"
    claude.complete.assert_called_once()


@pytest.mark.asyncio
async def test_ttl_expired_triggers_regeneration(db_session):
    user = await _make_user(db_session)
    sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="day-old",
        generated_at=datetime.now(UTC) - timedelta(
            hours=settings.nudge_cache_ttl_hours + 1
        ),
        input_signature=sig,
    ))
    await db_session.commit()

    claude = _fake_claude("fresh")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "fresh"


@pytest.mark.asyncio
async def test_llm_failure_with_existing_row_returns_stale(db_session):
    user = await _make_user(db_session)
    old_sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="stale body",
        generated_at=datetime.now(UTC) - timedelta(hours=48),
        input_signature=old_sig,
    ))
    await db_session.commit()

    claude = MagicMock()
    claude.complete = AsyncMock(side_effect=RuntimeError("api down"))

    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "stale body"
    assert out.is_fresh is False
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).scalar_one()
    assert row.body == "stale body"


@pytest.mark.asyncio
async def test_llm_failure_with_no_row_returns_static_fallback(db_session):
    user = await _make_user(db_session)
    claude = MagicMock()
    claude.complete = AsyncMock(side_effect=RuntimeError("api down"))

    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body
    assert out.is_fresh is False
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).first()
    assert row is None


def test_signature_is_stable_for_same_inputs():
    a = _build_signature(["AI協調", "API基礎"], "2:1", 5)
    b = _build_signature(["AI協調", "API基礎"], "2:1", 5)
    assert a == b and len(a) == 16


def test_signature_changes_when_inputs_change():
    base = _build_signature(["AI協調"], "2:1", 5)
    assert _build_signature(["API基礎"], "2:1", 5) != base
    assert _build_signature(["AI協調"], "3:1", 5) != base
    assert _build_signature(["AI協調"], "2:1", 6) != base
