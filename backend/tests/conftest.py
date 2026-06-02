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


@pytest_asyncio.fixture
async def auth_user(db_session):
    from app.core.security import hash_password
    from app.models.user import User
    from app.services.progress import initialize_progress

    user = User(
        email="alice@example.com",
        name="アリス",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.flush()
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(auth_user) -> str:
    from app.core.security import create_access_token

    return create_access_token(subject=str(auth_user.id))


@pytest_asyncio.fixture
async def auth_client(client, auth_token):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return client
