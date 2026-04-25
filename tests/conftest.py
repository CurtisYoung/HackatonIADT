from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Synchronous TestClient reused across all route tests."""
    with TestClient(app) as c:
        yield c
