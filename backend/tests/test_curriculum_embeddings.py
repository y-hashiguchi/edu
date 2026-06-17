"""Sprint 18 — curriculum embedding seed tests."""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.data.courses import runtime
from app.models.embedding import EMBEDDING_DIM, Embedding
from app.services.curriculum_embeddings import (
    build_embedding_items,
    prune_orphan_course_embeddings,
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


@pytest.mark.asyncio
async def test_prune_orphan_course_embeddings(
    db_session, seed_curriculum, default_course_id
):
    await runtime.reload_from_db(db_session)
    valid_ref = "course:ai-driven-dev:phase:1:task:0"
    orphan_ref = "course:ai-driven-dev:phase:1:task:99"
    vec = [0.0] * EMBEDDING_DIM
    for ref in (valid_ref, orphan_ref):
        db_session.add(
            Embedding(
                user_id=None,
                course_id=default_course_id,
                source_type="curriculum_task",
                source_ref=ref,
                phase=1,
                content="x",
                embedding=vec,
            )
        )
    await db_session.commit()

    pruned = await prune_orphan_course_embeddings(db_session, "ai-driven-dev")
    assert pruned == 1

    refs = (
        await db_session.execute(
            select(Embedding.source_ref).where(
                Embedding.course_id == default_course_id,
                Embedding.source_type == "curriculum_task",
            )
        )
    ).scalars().all()
    assert refs == [valid_ref]
