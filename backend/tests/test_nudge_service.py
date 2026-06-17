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
    COLD_START_BODY,
    TRANSITIONAL_BODY,
    _build_signature,
    get_or_generate,
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
async def test_cold_start_returns_static_without_calling_llm(db_session, default_course_id):
    user = await _make_user(db_session)
    claude = _fake_claude("UNUSED")
    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=[],
        top_recommendation_key=None,
        submission_count=0,
    )
    assert out.body == COLD_START_BODY
    assert out.is_fresh is True
    claude.complete.assert_not_called()
    row = (await db_session.execute(select(UserNudge).where(UserNudge.user_id == user.id))).first()
    assert row is None


@pytest.mark.asyncio
async def test_cache_miss_generates_and_persists(db_session, default_course_id):
    user = await _make_user(db_session)
    claude = _fake_claude("データ構造が伸びる Phase 2 タスク 1 をやろう。")
    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=["AI協調"],
        top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.is_fresh is True
    assert "Phase 2" in out.body
    row = (
        await db_session.execute(select(UserNudge).where(UserNudge.user_id == user.id))
    ).scalar_one()
    assert row.body == out.body
    assert len(row.input_signature) == 16


@pytest.mark.asyncio
async def test_cache_hit_within_ttl_does_not_call_llm(db_session, default_course_id):
    user = await _make_user(db_session)
    sig = _build_signature(default_course_id, ["AI協調"], "2:1", 5)
    db_session.add(
        UserNudge(
            user_id=user.id,
            course_id=default_course_id,
            body="cached body",
            generated_at=datetime.now(UTC),
            input_signature=sig,
        )
    )
    await db_session.commit()

    claude = _fake_claude("WOULD-BE-NEW")
    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=["AI協調"],
        top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "cached body"
    claude.complete.assert_not_called()


@pytest.mark.asyncio
async def test_signature_change_invalidates_cache_even_within_ttl(db_session, default_course_id):
    user = await _make_user(db_session)
    old_sig = _build_signature(default_course_id, ["AI協調"], "2:1", 5)
    db_session.add(
        UserNudge(
            user_id=user.id,
            course_id=default_course_id,
            body="stale",
            generated_at=datetime.now(UTC),
            input_signature=old_sig,
        )
    )
    await db_session.commit()

    claude = _fake_claude("regenerated body")
    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=["AI協調"],
        top_recommendation_key="3:2",  # changed
        submission_count=5,
    )
    assert out.body == "regenerated body"
    claude.complete.assert_called_once()


@pytest.mark.asyncio
async def test_ttl_expired_triggers_regeneration(db_session, default_course_id):
    user = await _make_user(db_session)
    sig = _build_signature(default_course_id, ["AI協調"], "2:1", 5)
    db_session.add(
        UserNudge(
            user_id=user.id,
            course_id=default_course_id,
            body="day-old",
            generated_at=datetime.now(UTC) - timedelta(hours=settings.nudge_cache_ttl_hours + 1),
            input_signature=sig,
        )
    )
    await db_session.commit()

    claude = _fake_claude("fresh")
    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=["AI協調"],
        top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "fresh"


@pytest.mark.asyncio
async def test_llm_failure_with_existing_row_returns_stale(db_session, default_course_id):
    user = await _make_user(db_session)
    old_sig = _build_signature(default_course_id, ["AI協調"], "2:1", 5)
    db_session.add(
        UserNudge(
            user_id=user.id,
            course_id=default_course_id,
            body="stale body",
            generated_at=datetime.now(UTC) - timedelta(hours=48),
            input_signature=old_sig,
        )
    )
    await db_session.commit()

    claude = MagicMock()
    claude.complete = AsyncMock(side_effect=RuntimeError("api down"))

    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=["AI協調"],
        top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "stale body"
    assert out.is_fresh is False
    row = (
        await db_session.execute(select(UserNudge).where(UserNudge.user_id == user.id))
    ).scalar_one()
    assert row.body == "stale body"


@pytest.mark.asyncio
async def test_llm_failure_with_no_row_returns_static_fallback(db_session, default_course_id):
    user = await _make_user(db_session)
    claude = MagicMock()
    claude.complete = AsyncMock(side_effect=RuntimeError("api down"))

    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=["AI協調"],
        top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body
    assert out.is_fresh is False
    row = (await db_session.execute(select(UserNudge).where(UserNudge.user_id == user.id))).first()
    assert row is None


def test_signature_is_stable_for_same_inputs(default_course_id):
    a = _build_signature(default_course_id, ["AI協調", "API基礎"], "2:1", 5)
    b = _build_signature(default_course_id, ["AI協調", "API基礎"], "2:1", 5)
    assert a == b and len(a) == 16


def test_signature_changes_when_inputs_change(default_course_id):
    base = _build_signature(default_course_id, ["AI協調"], "2:1", 5)
    assert _build_signature(default_course_id, ["API基礎"], "2:1", 5) != base
    assert _build_signature(default_course_id, ["AI協調"], "3:1", 5) != base
    assert _build_signature(default_course_id, ["AI協調"], "2:1", 6) != base


@pytest.mark.asyncio
async def test_transitional_state_returns_static_without_calling_llm(db_session, default_course_id):
    """MED-2 (sprint-5 follow-up): just past cold-start (submission_count
    >= 3) but no tag has hit MIN_TAG_SUBMISSIONS=2 yet, so weakness=[]
    and recommendations=[]. The XML prompt would be empty enough that
    Haiku hallucinates curriculum-irrelevant tasks (locally observed:
    "タスク4：基礎文法の動詞活用"). Skip the LLM and return a
    transitional static body; the cache row is NOT created so the
    next state transition (a 2nd tag-mate submission) gets an honest
    cache miss instead of stale transitional text."""
    user = await _make_user(db_session)
    claude = _fake_claude("UNUSED")

    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=[],
        top_recommendation_key=None,
        submission_count=5,
        recommendation_titles=[],
    )
    assert out.body == TRANSITIONAL_BODY
    assert out.is_fresh is True
    claude.complete.assert_not_called()
    row = (await db_session.execute(select(UserNudge).where(UserNudge.user_id == user.id))).first()
    assert row is None


@pytest.mark.asyncio
async def test_transitional_state_recommendation_titles_none_also_short_circuits(
    db_session,
    default_course_id,
):
    """recommendation_titles defaults to None when callers omit it;
    the transitional guard must treat that as empty too."""
    user = await _make_user(db_session)
    claude = _fake_claude("UNUSED")

    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=[],
        top_recommendation_key=None,
        submission_count=5,
        # recommendation_titles intentionally omitted
    )
    assert out.body == TRANSITIONAL_BODY
    claude.complete.assert_not_called()


@pytest.mark.asyncio
async def test_weakness_present_bypasses_transitional_state(db_session, default_course_id):
    """Regression: as soon as a single weakness tag is computed, the
    nudge path goes back to the LLM. The transitional guard must not
    swallow well-formed inputs."""
    user = await _make_user(db_session)
    claude = _fake_claude("Phase 2 task 1 をやろう")

    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=["AI協調"],
        top_recommendation_key=None,
        submission_count=5,
        recommendation_titles=[],
    )
    assert out.body == "Phase 2 task 1 をやろう"
    claude.complete.assert_called_once()


@pytest.mark.asyncio
async def test_recommendation_titles_present_bypasses_transitional_state(
    db_session,
    default_course_id,
):
    """Symmetric to the previous test: a non-empty recommendation set
    is enough context for the LLM, so we must not short-circuit even
    if weakness happens to be empty."""
    user = await _make_user(db_session)
    claude = _fake_claude("二分探索木に挑戦しよう")

    out = await get_or_generate(
        db_session,
        claude=claude,
        user_id=user.id,
        course_id=default_course_id,
        weakness_tags=[],
        top_recommendation_key="2:1",
        submission_count=5,
        recommendation_titles=["二分探索木の実装"],
    )
    assert out.body == "二分探索木に挑戦しよう"
    claude.complete.assert_called_once()
