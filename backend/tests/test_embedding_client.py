import pytest

from app.config import settings
from app.core.embedding_client import EMBEDDING_DIM, EmbeddingClient


@pytest.mark.asyncio
async def test_embed_returns_correct_dim():
    client = EmbeddingClient()
    vectors = await client.embed(["Gitとは何ですか"])
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIM


@pytest.mark.asyncio
async def test_embed_batch():
    client = EmbeddingClient()
    vectors = await client.embed(["Gitとは", "Pythonとは", "Vue.jsとは"])
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == EMBEDDING_DIM


@pytest.mark.asyncio
async def test_embed_empty_input_returns_empty():
    client = EmbeddingClient()
    vectors = await client.embed([])
    assert vectors == []


@pytest.mark.asyncio
async def test_stub_embed_is_deterministic():
    from app.core.embedding_stub import stub_embed_one

    a = stub_embed_one("Gitとは")
    b = stub_embed_one("Gitとは")
    c = stub_embed_one("Pythonとは")
    assert a == b
    assert a != c
    assert len(a) == EMBEDDING_DIM


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(
    settings.embedding_stub_mode,
    reason="semantic similarity requires real fastembed model",
)
async def test_similar_queries_have_higher_cosine_similarity():
    import numpy as np

    client = EmbeddingClient()
    vecs = await client.embed(
        ["Gitでブランチを切る方法", "Gitのブランチ作成手順", "Pythonの内包表記"]
    )
    a = np.array(vecs[0])
    b = np.array(vecs[1])
    c = np.array(vecs[2])

    sim_ab = a @ b / (np.linalg.norm(a) * np.linalg.norm(b))
    sim_ac = a @ c / (np.linalg.norm(a) * np.linalg.norm(c))
    assert sim_ab > sim_ac
