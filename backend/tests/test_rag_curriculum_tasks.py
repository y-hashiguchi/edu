"""Sprint 5: curriculum_task に絞った RAG ヘルパーのテスト。

既存 `search_context` は会話用（phase 必須）なので、recommendation
service が「全 phase 横断で task のみ」を引きたいケース専用に新規
関数を切る。"""

import pytest

from app.core.embedding_client import EmbeddingClient
from app.services.embedding import upsert_embeddings
from app.services.rag import search_curriculum_tasks


@pytest.fixture(scope="module")
def client():
    return EmbeddingClient()


@pytest.mark.asyncio
async def test_search_returns_phase_and_task_no_parsed_from_source_ref(
    db_session, client,
):
    items = [
        ("curriculum_task", "phase:1:task:0", 1, "Git でブランチを切る"),
        ("curriculum_task", "phase:2:task:1", 2, "Copilot で書く"),
        ("curriculum_task", "phase:3:task:2", 3, "AI とペアで実装する"),
        # ノイズ: curriculum_skill は除外されるべき
        ("curriculum_skill", "phase:1:skill:0", 1, "Git/GitHub"),
    ]
    await upsert_embeddings(db_session, client, user_id=None, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(
        db_session, client, query="Git でブランチを切る", limit=5,
    )
    assert all(h.phase in {1, 2, 3} for h in hits)
    assert all(1 <= h.task_no <= 3 for h in hits)
    assert hits[0].phase == 1 and hits[0].task_no == 1
    assert len(hits) <= 3  # curriculum_skill excluded


@pytest.mark.asyncio
async def test_search_returns_empty_on_blank_query(db_session, client):
    out = await search_curriculum_tasks(db_session, client, query="  ", limit=5)
    assert out == []


@pytest.mark.asyncio
async def test_search_caps_at_limit(db_session, client):
    items = [
        ("curriculum_task", f"phase:1:task:{i}", 1, f"題材{i}")
        for i in range(6)
    ]
    await upsert_embeddings(db_session, client, user_id=None, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(
        db_session, client, query="題材", limit=3,
    )
    assert len(hits) == 3


@pytest.mark.asyncio
async def test_search_skips_malformed_source_ref(db_session, client):
    """defensive: 過去データに混入した古い形式の source_ref を黙って捨てる"""
    items = [
        ("curriculum_task", "legacy-format", 1, "古い形式"),
        ("curriculum_task", "phase:1:task:0", 1, "新しい形式"),
    ]
    await upsert_embeddings(db_session, client, user_id=None, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(db_session, client, query="形式", limit=5)
    assert any(h.phase == 1 and h.task_no == 1 for h in hits)
    assert all(h.phase == 1 for h in hits)
