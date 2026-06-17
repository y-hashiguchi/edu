"""Deterministic embedding stub for CI / tests (Sprint 25).

Avoids HuggingFace model downloads and rate limits. Vectors are derived
from a SHA-256 hash of normalized text so identical inputs embed to the
same unit vector and CI stays offline-friendly.
"""

from __future__ import annotations

import hashlib
import math

EMBEDDING_DIM = 384


def stub_embed(texts: list[str]) -> list[list[float]]:
    return [stub_embed_one(text) for text in texts]


def stub_embed_one(text: str) -> list[float]:
    normalized = " ".join(text.strip().lower().split())
    vec: list[float] = []
    for dim in range(EMBEDDING_DIM):
        digest = hashlib.sha256(f"{normalized}|{dim}".encode()).digest()
        val = int.from_bytes(digest[:4], "big") / 2**32
        vec.append(val * 2 - 1)
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / mag for x in vec]
