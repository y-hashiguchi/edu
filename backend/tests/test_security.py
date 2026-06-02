import pytest
from jose import JWTError

from app.core import security


def test_hash_then_verify_returns_true():
    hashed = security.hash_password("hunter2-strong")
    assert security.verify_password("hunter2-strong", hashed)


def test_verify_returns_false_for_wrong_password():
    hashed = security.hash_password("hunter2-strong")
    assert not security.verify_password("wrong-password", hashed)


def test_hash_outputs_differ_for_same_input():
    a = security.hash_password("same")
    b = security.hash_password("same")
    assert a != b  # bcrypt の salt で差分


def test_create_then_decode_returns_subject():
    token = security.create_access_token(subject="user-123")
    assert security.decode_access_token(token) == "user-123"


def test_decode_raises_on_invalid_signature():
    token = security.create_access_token(subject="user-123")
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(JWTError):
        security.decode_access_token(tampered)


def test_decode_raises_on_expired_token():
    token = security.create_access_token(subject="user-123", expires_min=-1)
    with pytest.raises(JWTError):
        security.decode_access_token(token)


def test_decode_raises_on_missing_sub():
    from datetime import UTC, datetime, timedelta

    from jose import jwt

    from app.config import settings

    payload = {"exp": datetime.now(UTC) + timedelta(minutes=5)}
    bad_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(JWTError):
        security.decode_access_token(bad_token)
