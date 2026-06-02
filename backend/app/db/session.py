"""Async engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# NullPool: connections are not reused across event loops.
# pytest-asyncio creates a fresh loop per test, and asyncpg connections
# bound to a closed loop fail with "another operation is in progress".
engine = create_async_engine(
    settings.database_url, future=True, echo=False, poolclass=NullPool
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async DB session."""
    async with SessionLocal() as session:
        yield session
