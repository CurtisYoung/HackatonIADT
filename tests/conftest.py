from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """TestClient síncrono reutilizado em toda a suite de rotas."""
    with TestClient(app) as c:
        yield c
