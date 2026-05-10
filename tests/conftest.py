from __future__ import annotations

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

# Carrega o .env antes de importar a aplicação para que GEMINI_API_KEY
# esteja disponível para o GeminiClient durante a execução dos testes.
load_dotenv()

# Importa app original
from app.main import app as original_app  # noqa: E402

# Mocks globais
MOCK_REDIS = MagicMock()
MOCK_AI_CLIENT = AsyncMock()
MOCK_REPO = MagicMock()


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """Fixture que mocka todas as dependências automaticamente."""
    # Mock Redis
    from app.core.redis import get_redis_client
    monkeypatch.setattr(get_redis_client, "__call__", lambda: MOCK_REDIS)
    
    # Mock AI Client
    from app.infrastructure.ai_client import AIClient
    monkeypatch.setattr(AIClient, "__new__", lambda cls, *args, **kwargs: MOCK_AI_CLIENT)
    
    # Mock Repository
    from app.infrastructure.file_repository import FileOutputRepository
    monkeypatch.setattr(FileOutputRepository, "__new__", lambda cls, *args, **kwargs: MOCK_REPO)
    
    yield
    
    # Cleanup
    MOCK_REDIS.reset_mock()
    MOCK_AI_CLIENT.reset_mock()
    MOCK_REPO.reset_mock()


@pytest.fixture(scope="session")
def client() -> TestClient:
    """TestClient síncrono reutilizado em todos os testes de rotas."""
    # Criar cópia do app sem middleware problemático para testes
    from fastapi import FastAPI
    from app.api.routes import router
    
    test_app = FastAPI(
        title=original_app.title,
        description=original_app.description,
        version=original_app.version,
    )
    
    # Incluir apenas o router sem middlewares
    test_app.include_router(router)
    
    with TestClient(test_app) as c:
        yield c


@pytest.fixture
def mock_redis():
    """Fixture para acessar o mock do Redis."""
    return MOCK_REDIS


@pytest.fixture
def mock_ai_client():
    """Fixture para acessar o mock do AI Client."""
    return MOCK_AI_CLIENT


@pytest.fixture
def mock_repository():
    """Fixture para acessar o mock do Repository."""
    return MOCK_REPO
