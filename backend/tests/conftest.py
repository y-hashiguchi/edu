import os

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_MODEL", "claude-sonnet-4-5")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("BCRYPT_ROUNDS", "4")


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_db():
    """Create all tables once at session start, drop at end."""
    from app import models  # noqa: F401  ensures metadata registration
    from app.db.base import Base
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_setup_db):
    """Truncate all tables before each test, then yield an AsyncSession."""
    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )

    async with SessionLocal() as session:
        yield session
