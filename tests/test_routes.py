from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.routes import _get_gemini_client, _get_repository
from app.domain.repositories import OutputRepository
from app.domain.schemas import AIAnalysisOutput, IdentifiedComponent, ArchitecturalRisk, Recommendation
from app.main import app

ENDPOINT = "/analyze-diagram"

VALID_PAYLOAD: dict[str, str] = {
    "image_base64": "aW1hZ2VtX2Zha2VfYmFzZTY0",
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


def _mock_gemini_client() -> AsyncMock:
    mock = AsyncMock()
    mock.analyze_image.return_value = _FAKE_OUTPUT
    return mock


def _mock_repository() -> AsyncMock:
    mock = AsyncMock(spec=OutputRepository)
    mock.save.return_value = None
    return mock


# Override dependencies globally for all route tests
app.dependency_overrides[_get_gemini_client] = _mock_gemini_client
app.dependency_overrides[_get_repository] = _mock_repository


def test_analyze_diagram_returns_200_and_correct_schema(client: TestClient) -> None:
    """POST /analyze-diagram com payload válido deve retornar HTTP 200 e
    um JSON contendo exatamente as chaves definidas em AIAnalysisOutput."""
    response = client.post(ENDPOINT, json=VALID_PAYLOAD)

    assert response.status_code == 200

    body = response.json()
    assert EXPECTED_KEYS.issubset(body.keys()), (
        f"Missing keys in response: {EXPECTED_KEYS - body.keys()}"
    )


def test_analyze_diagram_fields_are_lists(client: TestClient) -> None:
    """Todos os campos do schema de saída devem ser listas."""
    response = client.post(ENDPOINT, json=VALID_PAYLOAD)
    body = response.json()

    for key in EXPECTED_KEYS:
        assert isinstance(body[key], list), (
            f"Field '{key}' should be a list, but is {type(body[key])}"
        )


def test_analyze_diagram_missing_image_base64_returns_422(client: TestClient) -> None:
    """Payload sem o campo obrigatório image_base64 deve retornar HTTP 422."""
    response = client.post(ENDPOINT, json={})

    assert response.status_code == 422


def test_analyze_diagram_accepts_optional_url(client: TestClient) -> None:
    """O campo url é opcional; enviá-lo não deve alterar o status_code."""
    payload = {**VALID_PAYLOAD, "url": "https://example.com/diagram.png"}
    response = client.post(ENDPOINT, json=payload)

    assert response.status_code == 200


def test_analyze_diagram_returns_503_when_ai_unavailable(client: TestClient) -> None:
    """Quando o cliente de IA lança ServerError retriável, o endpoint deve retornar HTTP 503."""
    from google.genai import errors as genai_errors

    def _mock_failing_gemini_client() -> AsyncMock:
        # Simula todos os modelos indisponíveis — ServerError com código 503.
        mock = AsyncMock()
        err = genai_errors.ServerError.__new__(genai_errors.ServerError)
        err.code = 503
        mock.analyze_image.side_effect = err
        return mock

    app.dependency_overrides[_get_gemini_client] = _mock_failing_gemini_client
    try:
        response = client.post(ENDPOINT, json=VALID_PAYLOAD)
        assert response.status_code == 503
    finally:
        # Restaura o mock original para não contaminar outros testes.
        app.dependency_overrides[_get_gemini_client] = _mock_gemini_client
