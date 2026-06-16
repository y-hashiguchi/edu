"""Sprint 9 — admin curriculum HTTP API tests."""

import pytest
from unittest.mock import AsyncMock


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
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    monkeypatch.setattr(
        "app.api.admin.curriculum.enqueue_curriculum_embeddings",
        AsyncMock(),
    )
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


# ---------------------------------------------------------------------------
# Sprint 15 — task structure API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_task_adds_at_end(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post("/api/admin/curriculum/ai-driven-dev/phases/1/tasks")
    assert res.status_code == 201
    body = res.json()
    assert body["task_no"] == 4
    assert body["title"] == "新しい Task"

    detail = client.get("/api/admin/curriculum/ai-driven-dev").json()
    p1 = detail["phases"][0]
    assert len(p1["tasks"]) == 4


@pytest.mark.asyncio
async def test_delete_task_returns_204(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.post("/api/admin/curriculum/ai-driven-dev/phases/1/tasks")
    res = client.delete(
        "/api/admin/curriculum/ai-driven-dev/phases/1/tasks/4"
    )
    assert res.status_code == 204
    detail = client.get("/api/admin/curriculum/ai-driven-dev").json()
    assert len(detail["phases"][0]["tasks"]) == 3


@pytest.mark.asyncio
async def test_delete_task_with_submissions_returns_409(
    client, admin_user, admin_token, auth_user, default_course_id, db_session
):
    from app.models.submission import Submission

    db_session.add(
        Submission(
            user_id=auth_user.id,
            course_id=default_course_id,
            phase=1,
            task_no=1,
            content="x",
        )
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.delete(
        "/api/admin/curriculum/ai-driven-dev/phases/1/tasks/1"
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_move_task_reorders(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post(
        "/api/admin/curriculum/ai-driven-dev/phases/1/tasks/3/move",
        json={"to_task_no": 1},
    )
    assert res.status_code == 200
    tasks = res.json()["tasks"]
    assert tasks[0]["task_no"] == 1


@pytest.mark.asyncio
async def test_move_phase_reorders(
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    async def _noop_full(slug: str) -> None:
        return None

    monkeypatch.setattr(
        "app.worker.enqueue.enqueue_curriculum_embeddings_full",
        _noop_full,
    )
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post(
        "/api/admin/curriculum/ai-driven-dev/phases/4/move",
        json={"to_phase_no": 1},
    )
    assert res.status_code == 204
    detail = client.get("/api/admin/curriculum/ai-driven-dev").json()
    assert detail["phases"][0]["phase_no"] == 1
    assert detail["phases"][0]["title"] != ""


# ---------------------------------------------------------------------------
# Sprint 17 — phase add / delete API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_phase_adds_at_end(
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    async def _noop_seed(db, slug, *, client=None):
        return 0

    monkeypatch.setattr(
        "app.services.curriculum_embeddings.seed_course_embeddings",
        _noop_seed,
    )
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post("/api/admin/curriculum/ai-driven-dev/phases")
    assert res.status_code == 201
    body = res.json()
    assert body["phase_no"] == 5
    assert len(body["tasks"]) == 1

    detail = client.get("/api/admin/curriculum/ai-driven-dev").json()
    assert len(detail["phases"]) == 5


@pytest.mark.asyncio
async def test_delete_phase_returns_204(
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    async def _noop_seed(db, slug, *, client=None):
        return 0

    monkeypatch.setattr(
        "app.services.curriculum_embeddings.seed_course_embeddings",
        _noop_seed,
    )
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.post("/api/admin/curriculum/ai-driven-dev/phases")
    res = client.delete("/api/admin/curriculum/ai-driven-dev/phases/5")
    assert res.status_code == 204
    detail = client.get("/api/admin/curriculum/ai-driven-dev").json()
    assert len(detail["phases"]) == 4


@pytest.mark.asyncio
async def test_delete_phase_with_submissions_returns_409(
    client, admin_user, admin_token, auth_user, default_course_id, db_session
):
    from app.models.submission import Submission

    db_session.add(
        Submission(
            user_id=auth_user.id,
            course_id=default_course_id,
            phase=1,
            task_no=1,
            content="x",
        )
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.delete("/api/admin/curriculum/ai-driven-dev/phases/1")
    assert res.status_code == 409



@pytest.mark.asyncio
async def test_create_course_returns_201(
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    async def _noop_seed(db, slug, *, client=None):
        return 0

    monkeypatch.setattr(
        "app.services.curriculum_embeddings.seed_course_embeddings",
        _noop_seed,
    )
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.post(
        "/api/admin/curriculum/courses",
        json={
            "slug": "new-course",
            "title": "新規コース",
            "description": "説明",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["slug"] == "new-course"
    assert body["phase_count"] == 4

    listed = client.get("/api/admin/curriculum/").json()["items"]
    assert any(it["slug"] == "new-course" for it in listed)

    detail = client.get("/api/admin/curriculum/new-course").json()
    assert len(detail["phases"]) == 4
    assert len(detail["phases"][0]["tasks"]) == 1


@pytest.mark.asyncio
async def test_create_course_duplicate_slug_returns_409(
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    async def _noop_seed(db, slug, *, client=None):
        return 0

    monkeypatch.setattr(
        "app.services.curriculum_embeddings.seed_course_embeddings",
        _noop_seed,
    )
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    payload = {"slug": "dup-course", "title": "A"}
    assert client.post("/api/admin/curriculum/courses", json=payload).status_code == 201
    res = client.post("/api/admin/curriculum/courses", json=payload)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_delete_course_returns_204(
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    async def _noop_seed(db, slug, *, client=None):
        return 0

    monkeypatch.setattr(
        "app.services.curriculum_embeddings.seed_course_embeddings",
        _noop_seed,
    )
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.post(
        "/api/admin/curriculum/courses",
        json={"slug": "del-me", "title": "Del"},
    )
    res = client.delete("/api/admin/curriculum/courses/del-me")
    assert res.status_code == 204
    assert client.get("/api/admin/curriculum/del-me").status_code == 404


@pytest.mark.asyncio
async def test_delete_protected_course_returns_409(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.delete("/api/admin/curriculum/courses/ai-driven-dev")
    assert res.status_code == 409
