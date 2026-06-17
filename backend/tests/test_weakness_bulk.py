"""Sprint 6: compute_top_weakness_tags_bulk.

admin users 一覧で N 名分の弱点 1 位タグを 1 クエリで返す。N+1 防止。"""

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.weakness import compute_top_weakness_tags_bulk


async def _make_user_id(db_session, email):
    user = User(email=email, name=email[:2], password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


@pytest.mark.asyncio
async def test_empty_user_ids_returns_empty_dict(db_session):
    out = await compute_top_weakness_tags_bulk(db_session, [])
    assert out == {}


@pytest.mark.asyncio
async def test_user_with_no_submissions_returns_none(db_session, default_course_id):
    uid = await _make_user_id(db_session, "z@e.com")
    out = await compute_top_weakness_tags_bulk(db_session, [(uid, default_course_id)])
    assert out == {uid: None}


@pytest.mark.asyncio
async def test_returns_lowest_average_tag_per_user(
    db_session,
    seed_multiple_learners_with_submissions,
    default_course_id,
):
    users = await seed_multiple_learners_with_submissions(
        [
            ("a@e.com", [(2, 1, 30), (2, 2, 40), (2, 3, 50)]),
            ("b@e.com", [(1, 1, 90), (2, 1, 30), (2, 2, 40)]),
        ]
    )
    pairs = [(u.id, default_course_id) for u, _ in users]
    out = await compute_top_weakness_tags_bulk(db_session, pairs)
    assert out[users[0][0].id] == "AI協調"
    assert out[users[1][0].id] == "AI協調"


@pytest.mark.asyncio
async def test_tie_breaker_by_tag_name_alphabetical(
    db_session,
    seed_multiple_learners_with_submissions,
    default_course_id,
):
    """同平均の eligible タグが複数あるとき、タグ名の辞書順で選ぶ。"""
    users = await seed_multiple_learners_with_submissions(
        [
            ("c@e.com", [(2, 3, 50), (3, 1, 50)]),
        ]
    )
    uid = users[0][0].id
    out = await compute_top_weakness_tags_bulk(db_session, [(uid, default_course_id)])
    assert out[uid] == "AI協調"


@pytest.mark.asyncio
async def test_bulk_returns_none_when_tags_below_min_submissions(
    db_session,
    seed_multiple_learners_with_submissions,
    default_course_id,
):
    """Sprint 6 MED-2: 1 件タグのみのとき bulk も None（fallback なし）。"""
    users = await seed_multiple_learners_with_submissions(
        [
            ("solo@e.com", [(1, 1, 40)]),
        ]
    )
    uid = users[0][0].id
    out = await compute_top_weakness_tags_bulk(db_session, [(uid, default_course_id)])
    assert out[uid] is None
