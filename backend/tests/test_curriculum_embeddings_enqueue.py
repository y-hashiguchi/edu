"""Sprint 20 — publish-time curriculum embedding refresh."""

import pytest

from app.config import settings
from app.worker.enqueue import enqueue_curriculum_embeddings


@pytest.mark.asyncio
async def test_enqueue_curriculum_embeddings_inline_when_async_disabled(
    monkeypatch,
):
    calls: list[tuple[str, list[str]]] = []

    async def fake_job(_ctx, course_slug, source_refs):
        calls.append((course_slug, source_refs))

    monkeypatch.setattr(settings, "grading_async_enabled", False)
    monkeypatch.setattr(
        "app.worker.enqueue.run_curriculum_embeddings_job",
        fake_job,
    )

    await enqueue_curriculum_embeddings(
        "ai-driven-dev",
        ["course:ai-driven-dev:phase:1:task:0"],
    )

    assert calls == [
        ("ai-driven-dev", ["course:ai-driven-dev:phase:1:task:0"]),
    ]


@pytest.mark.asyncio
async def test_enqueue_curriculum_embeddings_noop_on_empty_refs():
    await enqueue_curriculum_embeddings("ai-driven-dev", [])


@pytest.mark.asyncio
async def test_enqueue_curriculum_embeddings_full_inline_when_async_disabled(
    monkeypatch,
):
    calls: list[str] = []

    async def fake_job(_ctx, course_slug):
        calls.append(course_slug)

    monkeypatch.setattr(settings, "grading_async_enabled", False)
    monkeypatch.setattr(
        "app.worker.enqueue.run_curriculum_embeddings_full_job",
        fake_job,
    )

    from app.worker.enqueue import enqueue_curriculum_embeddings_full

    await enqueue_curriculum_embeddings_full("ai-driven-dev")
    assert calls == ["ai-driven-dev"]


@pytest.mark.asyncio
async def test_publish_enqueues_embedding_refresh(
    client, admin_user, admin_token, seed_curriculum, monkeypatch
):
    enqueued: list[tuple[str, list[str]]] = []

    async def fake_enqueue(course_slug, source_refs):
        enqueued.append((course_slug, list(source_refs)))

    monkeypatch.setattr(
        "app.api.admin.curriculum.enqueue_curriculum_embeddings",
        fake_enqueue,
    )

    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1/tasks/1",
        json={"title": "published embedding title"},
    )
    res = client.post("/api/admin/curriculum/ai-driven-dev/publish")
    assert res.status_code == 200
    assert enqueued == [
        (
            "ai-driven-dev",
            ["course:ai-driven-dev:phase:1:task:0"],
        ),
    ]
