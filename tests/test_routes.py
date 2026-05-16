from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes import _get_ai_client_factory, _get_repository, _get_redis
from app.domain.repositories import OutputRepository
from app.domain.schemas import AIAnalysisOutput, IdentifiedComponent, ArchitecturalRisk, Recommendation
from app.main import app

ENDPOINT = "/analyze/diagram/sync"
API_KEY = os.getenv("API_KEY", "default-secret-key")

VALID_PAYLOAD: dict = {
    "image_base64": "iVBORw0KGgp4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4",
    "file_path": "test.png",
}

EXPECTED_KEYS: frozenset[str] = frozenset(
    {"identified_components", "architectural_risks", "recommendations"}
)

_FAKE_OUTPUT = AIAnalysisOutput(
    identified_components=[
        IdentifiedComponent(id="c1", name="API Gateway", type="Gateway", function="Entry point"),
        IdentifiedComponent(id="c2", name="Database", type="Database", function="Storage"),
    ],
    architectural_risks=[
        ArchitecturalRisk(
            risk="Single point of failure in the API gateway",
            severity="High",
            impact="Total service outage",
            affected_components=["c1"],
        )
    ],
    recommendations=[
        Recommendation(action="Add redundancy", mitigates_risk="Single point of failure in the API gateway")
    ],
)


def _mock_ai_client() -> AsyncMock:
    mock = AsyncMock()
    mock.analyze_image.return_value = _FAKE_OUTPUT
    return mock


def _mock_repository() -> AsyncMock:
    mock = AsyncMock(spec=OutputRepository)
    mock.save.return_value = None
    return mock


def _mock_ai_client_factory() -> MagicMock:
    factory = MagicMock()
    factory.return_value = _mock_ai_client()
    return factory


@pytest.fixture
def _override_dependencies():
    app.dependency_overrides[_get_ai_client_factory] = _mock_ai_client_factory
    app.dependency_overrides[_get_redis] = lambda: MagicMock()
    app.dependency_overrides[_get_repository] = _mock_repository
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(_override_dependencies):
    with TestClient(app) as c:
        yield c


def test_analyze_diagram_returns_200_and_correct_schema(client: TestClient) -> None:
    response = client.post(
        ENDPOINT,
        json=VALID_PAYLOAD,
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200, response.json()

    body = response.json()
    assert EXPECTED_KEYS.issubset(body.keys())


def test_analyze_diagram_fields_are_lists(client: TestClient) -> None:
    response = client.post(
        ENDPOINT,
        json=VALID_PAYLOAD,
        headers={"X-API-Key": API_KEY}
    )
    body = response.json()

    for key in EXPECTED_KEYS:
        assert isinstance(body[key], list), f"Field '{key}' should be a list"


def test_analyze_diagram_missing_all_returns_422(client: TestClient) -> None:
    response = client.post(
        ENDPOINT,
        json={},
        headers={"X-API-Key": API_KEY}
    )

    assert response.status_code == 422


def test_analyze_diagram_with_file_path_only(client: TestClient, tmp_path) -> None:
    # Cria um arquivo temporário para o teste
    img_path = tmp_path / "test.png"
    # PNG minimal magic bytes
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 10)
    
    payload = {"file_path": str(img_path)}
    response = client.post(
        ENDPOINT,
        json=payload,
        headers={"X-API-Key": API_KEY}
    )

    assert response.status_code == 200, response.json()


def test_analyze_diagram_returns_500_when_validation_fails(client: TestClient) -> None:
    from pydantic import ValidationError

    def _mock_invalid_client() -> AsyncMock:
        mock = AsyncMock()
        mock.analyze_image.side_effect = ValidationError.from_exception_data(
            "AIAnalysisOutput", [{"type": "missing", "loc": ("test",), "msg": "test"}]
        )
        return mock

    def _mock_invalid_client_factory() -> MagicMock:
        factory = MagicMock()
        factory.return_value = _mock_invalid_client()
        return factory

    app.dependency_overrides[_get_ai_client_factory] = _mock_invalid_client_factory
    try:
        response = client.post(
            ENDPOINT,
            json=VALID_PAYLOAD,
            headers={"X-API-Key": API_KEY}
        )
        # ValidationError do Pydantic no use case resulta em 500 via o catch-all do FastAPI route
        assert response.status_code == 500
    finally:
        app.dependency_overrides[_get_ai_client_factory] = _mock_ai_client_factory
