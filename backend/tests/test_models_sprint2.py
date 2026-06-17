import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.embedding import EMBEDDING_DIM, Embedding
from app.models.submission import Submission
from app.models.user import User


async def _make_user(db, email: str = "alice@example.com") -> User:
    u = User(email=email, name="A", password_hash=hash_password("password123"))
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_submission_round_trip(db_session, default_course_id):
    user = await _make_user(db_session)
    db_session.add(
        Submission(
            user_id=user.id,
            course_id=default_course_id,
            phase=1,
            task_no=1,
            content="Hello",
            ai_feedback="OK",
            score=85,
        )
    )
    await db_session.commit()

    row = (await db_session.execute(select(Submission))).scalar_one()
    assert row.user_id == user.id
    assert row.score == 85


@pytest.mark.asyncio
async def test_submission_unique_per_user_phase_task(db_session, default_course_id):
    user = await _make_user(db_session)
    db_session.add(
        Submission(user_id=user.id, course_id=default_course_id, phase=1, task_no=1, content="A")
    )
    await db_session.commit()

    db_session.add(
        Submission(user_id=user.id, course_id=default_course_id, phase=1, task_no=1, content="B")
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_submission_score_range_constraint(db_session, default_course_id):
    user = await _make_user(db_session)
    db_session.add(
        Submission(
            user_id=user.id,
            course_id=default_course_id,
            phase=1,
            task_no=1,
            content="C",
            score=150,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_embedding_stores_vector(db_session, default_course_id):
    vec = [0.1] * EMBEDDING_DIM
    db_session.add(
        Embedding(
            user_id=None,
            course_id=default_course_id,
            source_type="curriculum_skill",
            source_ref="phase:1:skill:0",
            phase=1,
            content="Git / GitHub",
            embedding=vec,
        )
    )
    await db_session.commit()

    row = (await db_session.execute(select(Embedding))).scalar_one()
    assert len(row.embedding) == EMBEDDING_DIM
    assert pytest.approx(row.embedding[0]) == 0.1
