from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.routes import _get_gemini_client
from app.domain.schemas import AIAnalysisOutput
from app.main import app

ENDPOINT = "/analyze-diagram"

VALID_PAYLOAD: dict[str, str] = {
    "image_base64": "aW1hZ2VtX2Zha2VfYmFzZTY0",
}

EXPECTED_KEYS: frozenset[str] = frozenset(
    {"identified_components", "architectural_risks", "recommendations"}
)

_FAKE_OUTPUT = AIAnalysisOutput(
    identified_components=["API Gateway", "Database"],
    architectural_risks=["Single point of failure in the gateway."],
    recommendations=["Add redundancy to the gateway."],
)


def _mock_gemini_client() -> AsyncMock:
    mock = AsyncMock()
    mock.analyze_image.return_value = _FAKE_OUTPUT
    return mock


# Override the dependency globally for all route tests
app.dependency_overrides[_get_gemini_client] = _mock_gemini_client


def test_analyze_diagram_returns_200_and_correct_schema(client: TestClient) -> None:
    """POST /analyze-diagram with a valid payload should return HTTP 200 and
    a JSON containing exactly the keys defined in AIAnalysisOutput."""
    response = client.post(ENDPOINT, json=VALID_PAYLOAD)

    assert response.status_code == 200

    body = response.json()
    assert EXPECTED_KEYS.issubset(body.keys()), (
        f"Missing keys in response: {EXPECTED_KEYS - body.keys()}"
    )


def test_analyze_diagram_fields_are_lists(client: TestClient) -> None:
    """All output schema fields should be lists."""
    response = client.post(ENDPOINT, json=VALID_PAYLOAD)
    body = response.json()

    for key in EXPECTED_KEYS:
        assert isinstance(body[key], list), (
            f"Field '{key}' should be a list, but is {type(body[key])}"
        )


def test_analyze_diagram_missing_image_base64_returns_422(client: TestClient) -> None:
    """Payload without the required image_base64 field should return HTTP 422."""
    response = client.post(ENDPOINT, json={})

    assert response.status_code == 422


def test_analyze_diagram_accepts_optional_url(client: TestClient) -> None:
    """The url field is optional; sending it should not change the status_code."""
    payload = {**VALID_PAYLOAD, "url": "https://example.com/diagram.png"}
    response = client.post(ENDPOINT, json=payload)

    assert response.status_code == 200
