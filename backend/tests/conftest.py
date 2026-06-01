import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_MODEL", "claude-sonnet-4-5")


@pytest.fixture
def client() -> TestClient:
    from app.main import app
    return TestClient(app)
