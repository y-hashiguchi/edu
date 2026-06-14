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
# Sprint 8: keep grading synchronous in tests (no Redis worker required).
os.environ.setdefault("GRADING_ASYNC_ENABLED", "false")
# Sprint 9 LOW-2: disable cross-worker pub/sub in tests (no Redis listener).
os.environ.setdefault("CURRICULUM_CACHE_PUBSUB_ENABLED", "false")


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
    """Truncate all tables before each test, then yield an AsyncSession.

    Sprint 7: courses table is re-seeded after every truncate so
    enrollments / progress / submissions can FK into it."""
    from app.data.courses import COURSE_REGISTRY
    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )

    async with SessionLocal() as session:
        from app.models.course import Course
        for _slug, c in COURSE_REGISTRY.items():
            session.add(
                Course(
                    id=c.id,
                    slug=c.slug,
                    title=c.title,
                    description=c.description,
                    sort_order=c.sort_order,
                )
            )
        await session.commit()

        # Sprint 9: curriculum_phases / curriculum_tasks も毎テスト再 seed
        from app.models.curriculum_phase import CurriculumPhase
        from app.models.curriculum_task import CurriculumTask
        for _slug, c in COURSE_REGISTRY.items():
            for phase in c.phases:
                phase_row = CurriculumPhase(
                    course_id=c.id,
                    phase_no=phase.phase,
                    title=phase.title,
                    goal=phase.goal,
                    system_prompt=phase.system_prompt,
                )
                session.add(phase_row)
                await session.flush()
                for t in phase.tasks:
                    session.add(CurriculumTask(
                        phase_id=phase_row.id,
                        task_no=t.task_no,
                        title=t.title,
                        description=t.description,
                        skill_tags=list(t.skill_tags),
                        deliverable=t.deliverable,
                        week_label=t.week_label,
                    ))
        await session.commit()

        # Sprint 9: cache を test DB の内容で初期化
        from app.data.courses import runtime
        await runtime.reload_from_db(session)

        yield session


@pytest_asyncio.fixture
async def seed_curriculum(db_session):
    """Sprint 9 — Task 1-9 のテストが curriculum_phases / curriculum_tasks を
    必要とすることを明示するためのマーカー。実際の seed は db_session で済む。"""
    return db_session


@pytest_asyncio.fixture
async def default_course_id(db_session):
    """Sprint 7 — the ai-driven-dev course's fixed UUID."""
    import uuid
    return uuid.UUID("00000000-0000-4000-8000-000000000001")


@pytest_asyncio.fixture
async def se_course_id(db_session):
    """Sprint 7 — the ai-era-se course's fixed UUID (used by tests that
    exercise the second course)."""
    import uuid
    return uuid.UUID("00000000-0000-4000-8000-000000000002")


@pytest_asyncio.fixture
async def auth_user(db_session, default_course_id):
    from app.core.security import hash_password
    from app.data.courses import DEFAULT_COURSE_SLUG, get_course
    from app.models.user import User
    from app.services.enrollment import enroll_user
    from app.services.progress import initialize_progress_for_course

    user = User(
        email="alice@example.com",
        name="アリス",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.flush()
    await enroll_user(db_session, user_id=user.id, course_slug=DEFAULT_COURSE_SLUG)
    course_data = get_course(DEFAULT_COURSE_SLUG)
    await initialize_progress_for_course(
        db_session,
        user.id,
        default_course_id,
        [p.phase for p in course_data.phases],
    )
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
async def admin_user(db_session, default_course_id):
    """A standalone admin (separate row from `auth_user`) so a single test
    can spin up an admin AND a non-admin without email collisions."""
    from app.core.security import hash_password
    from app.data.courses import DEFAULT_COURSE_SLUG, get_course
    from app.models.user import User
    from app.services.enrollment import enroll_user
    from app.services.progress import initialize_progress_for_course

    user = User(
        email="instructor@example.com",
        name="講師",
        password_hash=hash_password("password123"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.flush()
    await enroll_user(db_session, user_id=user.id, course_slug=DEFAULT_COURSE_SLUG)
    course_data = get_course(DEFAULT_COURSE_SLUG)
    await initialize_progress_for_course(
        db_session,
        user.id,
        default_course_id,
        [p.phase for p in course_data.phases],
    )
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
async def seed_graded_submission(db_session, default_course_id):
    """Insert a Submission row + a GradingAttempt with status='graded'
    and the given score. Returns (submission, attempt) so tests can
    chain further mutations (e.g. re-grade, mark stale).

    Sprint 7: defaults to the ai-driven-dev course. Tests that need a
    different course can override via the optional ``course_id`` arg."""
    from datetime import UTC, datetime

    from app.models.grading_attempt import GradingAttempt
    from app.models.submission import Submission

    async def _seed(user, phase, task_no, score, course_id=None):
        sub = Submission(
            user_id=user.id,
            course_id=course_id or default_course_id,
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


@pytest_asyncio.fixture
async def seed_multiple_learners_with_submissions(
    db_session, seed_graded_submission, default_course_id
):
    """Spawn N learners each with M graded submissions.

    Returns a list of (User, list[(phase, task_no, score)]) for the
    bulk weakness aggregation tests."""
    from app.core.security import hash_password
    from app.data.courses import DEFAULT_COURSE_SLUG, get_course
    from app.models.user import User
    from app.services.enrollment import enroll_user
    from app.services.progress import initialize_progress_for_course

    async def _seed(specs):
        """specs: list of (email, list[(phase, task_no, score)])."""
        out = []
        course_data = get_course(DEFAULT_COURSE_SLUG)
        phase_numbers = [p.phase for p in course_data.phases]
        for email, subs in specs:
            user = User(
                email=email, name=email[:2],
                password_hash=hash_password("p"),
            )
            db_session.add(user)
            await db_session.flush()
            await enroll_user(
                db_session, user_id=user.id, course_slug=DEFAULT_COURSE_SLUG
            )
            await initialize_progress_for_course(
                db_session, user.id, default_course_id, phase_numbers
            )
            await db_session.commit()
            await db_session.refresh(user)
            for phase, task_no, score in subs:
                await seed_graded_submission(user, phase, task_no, score)
            out.append((user, subs))
        return out

    return _seed
