from __future__ import annotations

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Carrega o .env antes de importar a aplicação para que GEMINI_API_KEY
# esteja disponível para o GeminiClient durante a execução dos testes.
load_dotenv()

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    """TestClient síncrono reutilizado em todos os testes de rotas."""
    with TestClient(app) as c:
        yield c
