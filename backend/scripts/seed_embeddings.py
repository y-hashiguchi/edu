"""Seed curriculum content into the embeddings table.

Run via `make seed-embeddings` or `uv run python -m scripts.seed_embeddings`.
Idempotent: re-runs delete and re-insert rows with the same source_ref.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services.curriculum_embeddings import seed_all_course_embeddings  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        total = await seed_all_course_embeddings(db)
        await db.commit()
    print(f"Seeded {total} embedding rows.")


if __name__ == "__main__":
    asyncio.run(main())
