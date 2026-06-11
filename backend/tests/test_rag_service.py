import pytest

from app.core.embedding_client import EmbeddingClient
from app.core.security import hash_password
from app.models.user import User
from app.services.embedding import upsert_embeddings
from app.services.rag import RagHit, format_context, search_context


async def _make_user(db, email: str = "alice@example.com") -> User:
    u = User(email=email, name="A", password_hash=hash_password("password123"))
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_search_returns_phase_filtered_hits(db_session, default_course_id):
    user = await _make_user(db_session)
    client = EmbeddingClient()

    await upsert_embeddings(
        db_session,
        client,
        user_id=None,
        course_id=default_course_id,
        items=[
            ("curriculum_skill", "phase:1:skill:0", 1, "Git / GitHub の基礎"),
            ("curriculum_skill", "phase:1:skill:1", 1, "VSCode 拡張機能"),
            ("curriculum_skill", "phase:2:skill:0", 2, "Cursor IDE と Copilot"),
        ],
    )
    await upsert_embeddings(
        db_session,
        client,
        user_id=user.id,
        course_id=default_course_id,
        items=[
            ("chat_message", "msg-1", 1, "git branchの使い方を教えてください"),
        ],
    )
    await db_session.commit()

    results = await search_context(
        db_session, client, user_id=user.id, phase=1, query="Gitのブランチを切る", top_k=4
    )
    contents = [r.content for r in results]
    assert any("Git" in c for c in contents)
    # Phase 2 のグローバル row は除外されるはず
    assert not any("Cursor" in c for c in contents)


def test_format_context_produces_text():
    hits = [
        RagHit(source_type="curriculum_skill", content="Git / GitHub", score=0.9),
        RagHit(source_type="chat_message", content="昨日はpython基礎をやりました", score=0.7),
    ]
    text = format_context(hits)
    assert "Git / GitHub" in text
    assert "python基礎" in text
    assert "参考" in text


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_data(db_session):
    user = await _make_user(db_session)
    client = EmbeddingClient()
    results = await search_context(
        db_session, client, user_id=user.id, phase=1, query="anything", top_k=4
    )
    assert results == []


@pytest.mark.asyncio
async def test_format_context_empty():
    assert format_context([]) == ""
