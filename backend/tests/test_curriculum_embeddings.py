"""Sprint 18 — curriculum embedding seed tests."""

import pytest
from unittest.mock import AsyncMock, patch

from app.data.courses import runtime
from app.services.curriculum_embeddings import (
    build_embedding_items,
    seed_course_embeddings,
    seed_course_embeddings_refs,
)


def test_build_embedding_items_includes_tasks(seed_curriculum):
    items = build_embedding_items("ai-driven-dev")
    task_items = [it for it in items if it[0] == "curriculum_task"]
    assert len(task_items) >= 12
    assert task_items[0][1].startswith("course:ai-driven-dev:phase:")


@pytest.mark.asyncio
async def test_seed_course_embeddings_refs_filters_items(
    db_session, seed_curriculum
):
    await runtime.reload_from_db(db_session)
    refs = ["course:ai-driven-dev:phase:1:task:0"]
    with patch(
        "app.services.curriculum_embeddings.upsert_embeddings",
        new_callable=AsyncMock,
    ) as mock_upsert:
        count = await seed_course_embeddings_refs(
            db_session, "ai-driven-dev", refs
        )
    assert count == 1
    items = mock_upsert.await_args.kwargs["items"]
    assert len(items) == 1
    assert items[0][1] == refs[0]


@pytest.mark.asyncio
async def test_seed_course_embeddings_calls_upsert(db_session, seed_curriculum):
    await runtime.reload_from_db(db_session)
    with patch(
        "app.services.curriculum_embeddings.upsert_embeddings",
        new_callable=AsyncMock,
    ) as mock_upsert:
        count = await seed_course_embeddings(db_session, "ai-driven-dev")
    assert count > 0
    mock_upsert.assert_awaited_once()
