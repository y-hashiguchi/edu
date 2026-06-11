"""Sprint 5 recommendation service.

Glues unsubmitted task discovery + RAG ranking. The RAG call is
mocked so tests stay deterministic — exercising real fastembed inside
this suite would make it slow and flaky."""

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.data.courses import DEFAULT_COURSE_SLUG
from app.services.rag import CurriculumTaskHit
from app.services.recommendation import compute_recommendations


async def _make_user(db_session, email="r@e.com"):
    user = User(email=email, name="R", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_returns_empty_when_no_weakness_tags(db_session, default_course_id):
    user = await _make_user(db_session)
    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG, top_weakness_tags=[],
    )
    assert out == []


@pytest.mark.asyncio
async def test_returns_unsubmitted_hits_in_rag_order(
    db_session, seed_graded_submission, monkeypatch, default_course_id,
):
    """RAG が phase 1 task 1, phase 2 task 1, phase 3 task 2, phase 4 task 1
    を返した場合、未提出のものだけが上位 3 件として並ぶ。"""
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 50)  # submitted -> drop

    fake_hits = [
        CurriculumTaskHit(phase=1, task_no=1, score=0.95),  # 提出済 -> drop
        CurriculumTaskHit(phase=2, task_no=1, score=0.80),
        CurriculumTaskHit(phase=3, task_no=2, score=0.70),
        CurriculumTaskHit(phase=4, task_no=1, score=0.60),
    ]

    async def fake_search(db, client, *, query, limit):
        return fake_hits

    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )

    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        top_weakness_tags=["API基礎"],
    )
    coords = [(r.phase, r.task_no) for r in out]
    assert coords == [(2, 1), (3, 2), (4, 1)]


@pytest.mark.asyncio
async def test_match_tag_is_set_when_primary_tag_present_else_null(
    db_session, monkeypatch, default_course_id,
):
    """phase 2 task 1 has tags [AI協調, API基礎]: query 'API基礎' → match_tag
    set. phase 4 task 1 has [LLM活用]: match_tag None."""
    user = await _make_user(db_session)

    async def fake_search(db, client, *, query, limit):
        return [
            CurriculumTaskHit(phase=2, task_no=1, score=0.9),
            CurriculumTaskHit(phase=4, task_no=1, score=0.5),
        ]

    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )
    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        top_weakness_tags=["API基礎"],
    )
    by_key = {(r.phase, r.task_no): r for r in out}
    assert by_key[(2, 1)].match_tag == "API基礎"
    assert by_key[(4, 1)].match_tag is None


@pytest.mark.asyncio
async def test_caps_at_top_3(db_session, monkeypatch, default_course_id):
    user = await _make_user(db_session)

    async def fake_search(db, client, *, query, limit):
        return [
            CurriculumTaskHit(phase=p, task_no=t, score=1.0 - 0.1 * i)
            for i, (p, t) in enumerate([(1, 1), (1, 2), (1, 3), (2, 1), (2, 2)])
        ]
    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )
    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        top_weakness_tags=["AI協調"],
    )
    assert len(out) == 3


@pytest.mark.asyncio
async def test_returns_empty_when_all_tasks_submitted(
    db_session, seed_graded_submission, monkeypatch, default_course_id,
):
    user = await _make_user(db_session)
    for p in (1, 2, 3, 4):
        for t in (1, 2, 3):
            await seed_graded_submission(user, p, t, 70)

    async def fake_search(db, client, *, query, limit):
        return [CurriculumTaskHit(phase=1, task_no=1, score=0.99)]

    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )
    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, course_id=default_course_id,
        course_slug=DEFAULT_COURSE_SLUG,
        top_weakness_tags=["Git/GitHub"],
    )
    assert out == []
