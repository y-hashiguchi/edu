"""Sprint 5: curriculum_task に絞った RAG ヘルパーのテスト。

既存 `search_context` は会話用（phase 必須）なので、recommendation
service が「全 phase 横断で task のみ」を引きたいケース専用に新規
関数を切る。"""

import pytest

from app.core.embedding_client import EmbeddingClient
from app.services.embedding import upsert_embeddings
from app.services.rag import parse_curriculum_task_coords, search_curriculum_tasks


@pytest.fixture(scope="module")
def client():
    return EmbeddingClient()


def test_parse_curriculum_task_coords_accepts_course_scoped_ref():
    assert parse_curriculum_task_coords("course:ai-era-se:phase:2:task:0") == (2, 1)
    assert parse_curriculum_task_coords("phase:1:task:2") == (1, 3)
    assert parse_curriculum_task_coords("legacy-format") is None


@pytest.mark.asyncio
async def test_search_parses_course_scoped_source_ref(
    db_session, client, default_course_id,
):
    items = [
        (
            "curriculum_task",
            "course:ai-driven-dev:phase:2:task:0",
            2,
            "Cursor IDEで顧客管理API",
        ),
    ]
    await upsert_embeddings(
        db_session, client, user_id=None, course_id=default_course_id, items=items
    )
    await db_session.commit()

    hits = await search_curriculum_tasks(
        db_session,
        client,
        query="Cursor IDE",
        limit=5,
        course_id=default_course_id,
    )
    assert hits[0].phase == 2 and hits[0].task_no == 1


@pytest.mark.asyncio
async def test_search_returns_phase_and_task_no_parsed_from_source_ref(
    db_session, client, default_course_id,
):
    items = [
        ("curriculum_task", "phase:1:task:0", 1, "Git でブランチを切る"),
        ("curriculum_task", "phase:2:task:1", 2, "Copilot で書く"),
        ("curriculum_task", "phase:3:task:2", 3, "AI とペアで実装する"),
        # ノイズ: curriculum_skill は除外されるべき
        ("curriculum_skill", "phase:1:skill:0", 1, "Git/GitHub"),
    ]
    await upsert_embeddings(db_session, client, user_id=None, course_id=default_course_id, items=items)
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
async def test_search_caps_at_limit(db_session, client, default_course_id):
    items = [
        ("curriculum_task", f"phase:1:task:{i}", 1, f"題材{i}")
        for i in range(6)
    ]
    await upsert_embeddings(db_session, client, user_id=None, course_id=default_course_id, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(
        db_session, client, query="題材", limit=3,
    )
    assert len(hits) == 3


@pytest.mark.asyncio
async def test_search_skips_malformed_source_ref(db_session, client, default_course_id):
    """defensive: 過去データに混入した古い形式の source_ref を黙って捨てる"""
    items = [
        ("curriculum_task", "legacy-format", 1, "古い形式"),
        ("curriculum_task", "phase:1:task:0", 1, "新しい形式"),
    ]
    await upsert_embeddings(db_session, client, user_id=None, course_id=default_course_id, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(db_session, client, query="形式", limit=5)
    assert any(h.phase == 1 and h.task_no == 1 for h in hits)
    assert all(h.phase == 1 for h in hits)


@pytest.mark.asyncio
async def test_oversized_query_is_truncated_before_embedding(db_session):
    """MED-1 (sprint-5 follow-up): the query passed to fastembed must be
    capped at `settings.embed_query_max_chars` so a deliberately long
    payload cannot tie up the asyncio.to_thread pool. Verifies the cap
    by capturing what `client.embed` actually receives."""
    from app.config import settings
    from app.services.rag import search_curriculum_tasks

    captured: list[list[str]] = []

    class CapturingClient:
        async def embed(self, texts):
            captured.append(list(texts))
            # 384-dim zero vector — distance becomes 1.0, results
            # ordering is irrelevant for this assertion.
            return [[0.0] * 384 for _ in texts]

    cap = settings.embed_query_max_chars
    long_query = "あ" * (cap + 200)

    await search_curriculum_tasks(
        db_session, CapturingClient(), query=long_query, limit=3,
    )
    assert len(captured) == 1
    assert len(captured[0][0]) == cap


@pytest.mark.asyncio
async def test_normal_length_query_passes_through_unchanged(db_session):
    """Regression: queries below the cap are forwarded verbatim. Prevents
    accidentally truncating short Japanese queries on a future config
    change."""
    from app.services.rag import search_curriculum_tasks

    captured: list[list[str]] = []

    class CapturingClient:
        async def embed(self, texts):
            captured.append(list(texts))
            return [[0.0] * 384 for _ in texts]

    short = "Git/GitHub を扱うタスク"
    await search_curriculum_tasks(
        db_session, CapturingClient(), query=short, limit=3,
    )
    assert captured[0][0] == short


@pytest.mark.asyncio
async def test_search_context_also_truncates_oversized_query(db_session, auth_user):
    """search_context (the conversational RAG entry point) must apply
    the same cap. It is the more exposed endpoint — its query comes
    directly from user-controlled chat input."""
    from app.config import settings
    from app.services.rag import search_context

    captured: list[list[str]] = []

    class CapturingClient:
        async def embed(self, texts):
            captured.append(list(texts))
            return [[0.0] * 384 for _ in texts]

    cap = settings.embed_query_max_chars
    long_query = "x" * (cap + 50)

    await search_context(
        db_session, CapturingClient(),
        user_id=auth_user.id, phase=1, query=long_query, top_k=4,
    )
    assert len(captured[0][0]) == cap


@pytest.mark.asyncio
async def test_source_ref_with_extra_segments_is_dropped(db_session, client, default_course_id):
    """LOW-3 (sprint-5 follow-up): a 5-segment source_ref (e.g. a future
    A/B-variant schema like phase:1:task:0:variant:a) must be silently
    dropped, NOT yielded as a partial CurriculumTaskHit. The previous
    tuple-unpack would have raised ValueError on the unpack and dropped
    it the same way, but only by accident — an explicit length check
    makes the contract clear and survives a future schema with exactly
    4 colons in a non-phase form."""
    items = [
        ("curriculum_task", "phase:1:task:0:variant:a", 1, "5 セグメント形式"),
        ("curriculum_task", "phase:1:task:0", 1, "正しい形式"),
        # 3 segments — neither old nor expected new shape
        ("curriculum_task", "phase:1:task", 1, "3 セグメント形式"),
        # not "phase" prefix
        ("curriculum_task", "skill:1:task:0", 1, "間違った prefix"),
    ]
    await upsert_embeddings(db_session, client, user_id=None, course_id=default_course_id, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(
        db_session, client, query="形式", limit=10,
    )
    # Only the well-formed row survives.
    coords = [(h.phase, h.task_no) for h in hits]
    assert coords == [(1, 1)]
