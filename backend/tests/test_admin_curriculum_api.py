"""Sprint 9 — admin curriculum HTTP API tests."""

import pytest


@pytest.mark.asyncio
async def test_list_requires_admin(client, auth_user, auth_token, seed_curriculum):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/admin/curriculum/")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_returns_courses_with_zero_drafts(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/curriculum/")
    assert res.status_code == 200
    items = res.json()["items"]
    slugs = [it["slug"] for it in items]
    assert "ai-driven-dev" in slugs
    assert all(it["pending_draft_count"] == 0 for it in items)


@pytest.mark.asyncio
async def test_detail_returns_phases_and_tasks(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/curriculum/ai-driven-dev")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "ai-driven-dev"
    assert len(body["phases"]) == 4
    p1 = body["phases"][0]
    assert p1["phase_no"] == 1
    assert len(p1["tasks"]) == 3
    assert p1["draft_title"] is None  # 初期は draft なし


@pytest.mark.asyncio
async def test_put_phase_records_draft(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1",
        json={"title": "新しい Phase 1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["draft_title"] == "新しい Phase 1"
    assert body["title"] != "新しい Phase 1"  # published はまだ未更新


@pytest.mark.asyncio
async def test_put_task_records_draft_skill_tags(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1/tasks/1",
        json={"skill_tags": ["NEW_TAG", "NEW_TAG", "ANOTHER"]},
    )
    assert res.status_code == 200
    body = res.json()
    # dedup されている
    assert body["draft_skill_tags"] == ["NEW_TAG", "ANOTHER"]


@pytest.mark.asyncio
async def test_publish_promotes_drafts_idempotent(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1",
        json={"title": "publish me"},
    )
    res = client.post("/api/admin/curriculum/ai-driven-dev/publish")
    assert res.status_code == 200
    body = res.json()
    assert body["published_phase_count"] == 1

    # 2 度目の publish は 0 件 (idempotent)
    res2 = client.post("/api/admin/curriculum/ai-driven-dev/publish")
    assert res2.status_code == 200
    assert res2.json()["published_phase_count"] == 0


@pytest.mark.asyncio
async def test_discard_drafts_returns_204(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1",
        json={"title": "discard"},
    )
    res = client.post("/api/admin/curriculum/ai-driven-dev/draft")
    assert res.status_code == 204


# ---------------------------------------------------------------------------
# Sprint 9 follow-up LOW-1 — course_slug fast-fail regex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detail_rejects_invalid_slug_format(
    client, admin_user, admin_token, seed_curriculum
):
    """空白 / 大文字 / 過長スラッグは DB を叩く前に 422。"""
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    # uppercase
    res = client.get("/api/admin/curriculum/INVALID")
    assert res.status_code == 422
    # special characters
    res = client.get("/api/admin/curriculum/abc!")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_put_phase_rejects_invalid_slug(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.put(
        "/api/admin/curriculum/INVALID%20SLUG/phases/1",
        json={"title": "x"},
    )
    assert res.status_code == 422
