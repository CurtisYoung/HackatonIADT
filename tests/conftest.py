from __future__ import annotations

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import sys

# Mock verify_api_key antes de importar qualquer módulo que use router
def mock_verify_api_key(x_api_key: str = None):
    # Always accept any API key in tests
    return

# Injeta o mock no sys.modules antes do import
import types
mock_module = types.ModuleType('app.api.routes_mock')
sys.modules['app.api.routes_mock'] = mock_module

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
    
    # Mock API key verification to always succeed
    import app.api.routes
    original_verify_api_key = app.api.routes.verify_api_key
    
    def mock_verify_api_key(x_api_key: str = None):
        # Always accept any API key in tests
        return
    
    monkeypatch.setattr(app.api.routes, "verify_api_key", mock_verify_api_key)
    
    # Mock background task function to prevent ExceptionGroup
    original_run_analysis = app.api.routes._run_analysis_in_background
    
    async def mock_run_analysis(*args, **kwargs):
        # Simula execução bem-sucedida sem exceções
        task_id = args[0]
        redis_client = args[2]
        # Simula conclusão bem-sucedida
        redis_client.set(task_id, '{"status": "completed", "result": "{}"}')
    
    monkeypatch.setattr(app.api.routes, "_run_analysis_in_background", mock_run_analysis)
    
    yield
    
    # Restaura funções originais
    monkeypatch.setattr(app.api.routes, "verify_api_key", original_verify_api_key)
    monkeypatch.setattr(app.api.routes, "_run_analysis_in_background", original_run_analysis)
    
    # Cleanup
    MOCK_REDIS.reset_mock()
    MOCK_AI_CLIENT.reset_mock()
    MOCK_REPO.reset_mock()


@pytest.fixture(scope="session")
def client() -> TestClient:
    """TestClient síncrono reutilizado em todos os testes de rotas."""
    # Criar app de teste usando o app original mas com dependency overrides
    from fastapi import FastAPI
    from app.main import app
    
    # Criar cópia do app
    test_app = FastAPI(
        title=app.title,
        description=app.description,
        version=app.version,
    )
    
    # Copiar rotas
    for route in app.routes:
        test_app.routes.append(route)
    
    # Override da verificação de API key para sempre passar
    from app.api.routes import verify_api_key
    
    def mock_verify_api_key(x_api_key: str = None):
        return
    
    # Aplicar override
    test_app.dependency_overrides[verify_api_key] = mock_verify_api_key
    
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
