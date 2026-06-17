"""Embedding client wrapping fastembed multilingual model.

The TextEmbedding constructor is heavy (downloads ONNX model on first
use), so we lazy-init a process-wide singleton. Embedding is CPU-bound;
we wrap with asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
from threading import Lock

from fastembed import TextEmbedding

from app.config import settings
from app.core.embedding_stub import stub_embed

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

_model: TextEmbedding | None = None
_init_lock = Lock()


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        with _init_lock:
            if _model is None:
                _model = TextEmbedding(EMBEDDING_MODEL)
    return _model


class EmbeddingClient:
    """Thin async facade around fastembed."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if settings.embedding_stub_mode:
            return stub_embed(texts)

        def _do() -> list[list[float]]:
            model = _get_model()
            return [vec.tolist() for vec in model.embed(texts)]

        return await asyncio.to_thread(_do)


def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()
