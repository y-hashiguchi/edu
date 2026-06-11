import asyncio
from datetime import UTC, datetime, timedelta

from jose import jwt
from sqlalchemy import select

from app.config import settings


def test_register_creates_user_and_progress(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "name": "アリス",
            "password": "password123", "course_slug": "ai-driven-dev"
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "アリス"
    assert "id" in body and "created_at" in body


def test_register_password_is_hashed(client, db_session):
    client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "name": "アリス",
            "password": "password123", "course_slug": "ai-driven-dev"
        },
    )

    async def fetch():
        from app.db.session import SessionLocal
        from app.models.user import User

        async with SessionLocal() as session:
            row = (await session.execute(select(User))).scalar_one()
            return row.password_hash

    hashed = asyncio.run(fetch())
    assert hashed != "password123"
    assert hashed.startswith("$2")


def test_register_progress_rows_are_seeded(client, db_session):
    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "password123", "course_slug": "ai-driven-dev"},
    )

    async def fetch():
        from app.db.session import SessionLocal
        from app.models.progress import Progress

        async with SessionLocal() as session:
            rows = (
                (await session.execute(select(Progress).order_by(Progress.phase)))
                .scalars()
                .all()
            )
            return [(r.phase, r.status) for r in rows]

    rows = asyncio.run(fetch())
    assert rows == [
        (1, "in_progress"),
        (2, "locked"),
        (3, "locked"),
        (4, "locked"),
    ]


def test_register_returns_409_on_duplicate_email(client, db_session):
    payload = {"email": "alice@example.com", "name": "A", "password": "password123", "course_slug": "ai-driven-dev"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_register_returns_422_on_short_password(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "abc"},
    )
    assert response.status_code == 422


def test_register_returns_422_on_invalid_email(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "name": "A", "password": "password123", "course_slug": "ai-driven-dev"},
    )
    assert response.status_code == 422


def test_login_returns_token_on_valid_credentials(client, db_session):
    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "password123", "course_slug": "ai-driven-dev"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123", "course_slug": "ai-driven-dev"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_returns_401_on_wrong_password(client, db_session):
    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "password123", "course_slug": "ai-driven-dev"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "WRONG"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_returns_401_on_unknown_email(client, db_session):
    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "password123", "course_slug": "ai-driven-dev"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_me_returns_current_user(auth_client, auth_user):
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == auth_user.email
    assert body["name"] == auth_user.name


def test_me_returns_401_without_token(client, db_session):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_401_with_invalid_signature(client, auth_token):
    tampered = auth_token[:-2] + ("aa" if not auth_token.endswith("aa") else "bb")
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert response.status_code == 401


def test_me_returns_401_with_expired_token(client, auth_user):
    payload = {
        "sub": str(auth_user.id),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    expired = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401
