"""Sprint 6: GET /api/admin/users の response に top_weakness_tag が
含まれる。bulk 集計で N+1 を避ける。"""

import pytest

from app.core.security import create_access_token, hash_password
from app.models.user import User


def _auth(client, user_id):
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


@pytest.mark.asyncio
async def test_admin_users_list_includes_top_weakness_tag_field(
    client, db_session, admin_user,
):
    learner = User(
        email="l@e.com", name="L",
        password_hash=hash_password("p"),
    )
    db_session.add(learner)
    await db_session.commit()

    _auth(client, admin_user.id)
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    items = r.json()["items"]
    by_email = {u["email"]: u for u in items}
    assert "top_weakness_tag" in by_email["l@e.com"]
    assert by_email["l@e.com"]["top_weakness_tag"] is None


@pytest.mark.asyncio
async def test_admin_users_list_returns_top_weakness_for_submitted_learner(
    client, db_session, admin_user, seed_multiple_learners_with_submissions,
):
    await seed_multiple_learners_with_submissions([
        ("a@e.com", [(2, 1, 30), (2, 2, 40), (2, 3, 50)]),
    ])

    _auth(client, admin_user.id)
    r = client.get("/api/admin/users")
    items = r.json()["items"]
    by_email = {u["email"]: u for u in items}
    assert by_email["a@e.com"]["top_weakness_tag"] == "AI協調"
