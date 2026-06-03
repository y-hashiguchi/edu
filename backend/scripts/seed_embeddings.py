"""Seed curriculum content into the embeddings table.

Run via `make seed-embeddings` or `uv run python -m scripts.seed_embeddings`.
Idempotent: re-runs delete and re-insert rows with the same source_ref.
"""

import asyncio
import sys
from pathlib import Path

# Allow `python scripts/seed_embeddings.py` from the backend root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.embedding_client import EmbeddingClient  # noqa: E402
from app.data.curriculum import CURRICULUM
from app.db.session import SessionLocal
from app.services.embedding import upsert_embeddings


async def main() -> None:
    client = EmbeddingClient()
    items: list[tuple[str, str, int | None, str]] = []
    for phase_no, phase in CURRICULUM.items():
        for i, skill in enumerate(phase["skills"]):
            items.append(("curriculum_skill", f"phase:{phase_no}:skill:{i}", phase_no, skill))
        for i, task in enumerate(phase["tasks"]):
            items.append(("curriculum_task", f"phase:{phase_no}:task:{i}", phase_no, task))

    async with SessionLocal() as db:
        await upsert_embeddings(db, client, user_id=None, items=items)
        await db.commit()

    print(f"Seeded {len(items)} embedding rows.")


if __name__ == "__main__":
    asyncio.run(main())
