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
# Disable per-IP rate limiting by default — individual tests opt in by
# toggling `limiter.enabled = True` in their own setup. With ~100 multipart
# POSTs flying through the test client, leaving the live 10/minute cap on
# would surface 429s in unrelated assertions.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


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


@pytest_asyncio.fixture
async def admin_user(db_session):
    """A standalone admin (separate row from `auth_user`) so a single test
    can spin up an admin AND a non-admin without email collisions."""
    from app.core.security import hash_password
    from app.models.user import User
    from app.services.progress import initialize_progress

    user = User(
        email="instructor@example.com",
        name="講師",
        password_hash=hash_password("password123"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.flush()
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user) -> str:
    from app.core.security import create_access_token
    return create_access_token(subject=str(admin_user.id))


@pytest_asyncio.fixture
async def admin_client(client, admin_token):
    """Use this when a test needs admin-side access end-to-end.
    Tests that need BOTH admin and learner access in the same test should
    drive the Authorization header manually instead of mixing this
    fixture with `auth_client` — the two share one TestClient and would
    overwrite each other's header."""
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client


@pytest_asyncio.fixture
async def seed_graded_submission(db_session):
    """Insert a Submission row + a GradingAttempt with status='graded'
    and the given score. Returns (submission, attempt) so tests can
    chain further mutations (e.g. re-grade, mark stale)."""
    from datetime import UTC, datetime

    from app.models.grading_attempt import GradingAttempt
    from app.models.submission import Submission

    async def _seed(user, phase, task_no, score):
        sub = Submission(
            user_id=user.id,
            phase=phase,
            task_no=task_no,
            content=f"essay phase{phase} task{task_no}",
            submitted_at=datetime.now(UTC),
        )
        db_session.add(sub)
        await db_session.flush()
        att = GradingAttempt(
            submission_id=sub.id,
            status="graded",
            score=score,
            feedback="ok",
            model_name="claude-sonnet-4-5",
        )
        db_session.add(att)
        await db_session.commit()
        await db_session.refresh(sub)
        await db_session.refresh(att)
        return sub, att

    return _seed
