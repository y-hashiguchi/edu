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
from app.data.courses import COURSE_REGISTRY
from app.data.curriculum import CURRICULUM
from app.db.session import SessionLocal
from app.services.embedding import upsert_embeddings


async def main() -> None:
    client = EmbeddingClient()
    # Sprint 7: seed embeddings for each course separately so RAG search
    # can scope by course_id. ai-driven-dev keeps the legacy source_ref
    # format for backward compatibility; ai-era-se uses a course-scoped
    # format. (Migrating ai-driven-dev to the new format is a follow-up.)
    async with SessionLocal() as db:
        total = 0
        for slug, course in COURSE_REGISTRY.items():
            items: list[tuple[str, str, int | None, str]] = []
            if slug == "ai-driven-dev":
                # Preserve legacy source_ref format for existing rows
                for phase_no, phase in CURRICULUM.items():
                    for i, skill in enumerate(phase["skills"]):
                        items.append(("curriculum_skill", f"phase:{phase_no}:skill:{i}", phase_no, skill))
                    for i, task in enumerate(phase["tasks"]):
                        items.append(
                            ("curriculum_task", f"phase:{phase_no}:task:{i}", phase_no, task["title"])
                        )
            else:
                # Course-scoped source_ref for new courses
                for phase in course.phases:
                    for i, task in enumerate(phase.tasks):
                        items.append(
                            (
                                "curriculum_task",
                                f"course:{slug}:phase:{phase.phase}:task:{i}",
                                phase.phase,
                                task.title,
                            )
                        )
            await upsert_embeddings(
                db, client, user_id=None, course_id=course.id, items=items
            )
            total += len(items)
        await db.commit()

    print(f"Seeded {total} embedding rows.")


if __name__ == "__main__":
    asyncio.run(main())
