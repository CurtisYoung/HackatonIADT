from __future__ import annotations
import json
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import _get_redis, _get_ai_client, _get_repository
from app.domain.schemas import AIAnalysisOutput, IdentifiedComponent, ArchitecturalRisk, Recommendation

# Mock objects
_MOCK_REDIS = MagicMock()
_MOCK_AI_CLIENT = AsyncMock()
_MOCK_REPO = MagicMock()

_FAKE_OUTPUT = AIAnalysisOutput(
    identified_components=[
        IdentifiedComponent(id="c1", name="API Gateway", type="Gateway", function="Entry point"),
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

@pytest.fixture
def setup_overrides():
    app.dependency_overrides[_get_redis] = lambda: _MOCK_REDIS
    app.dependency_overrides[_get_ai_client] = lambda: _MOCK_AI_CLIENT
    app.dependency_overrides[_get_repository] = lambda: _MOCK_REPO
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client(setup_overrides):
    with TestClient(app) as c:
        yield c

def test_analyze_diagram_async_creates_task(client: TestClient):
    # Setup
    _MOCK_REDIS.set.return_value = True
    payload = {"image_base64": "aW1hZ2VtX2Zha2VfYmFzZTY0"}
    
    # Execute
    response = client.post("/analyze/diagram/async", json=payload)
    
    # Assert
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "processing"
    assert _MOCK_REDIS.set.called

def test_get_analysis_status_not_found(client: TestClient):
    # Setup
    _MOCK_REDIS.get.return_value = None
    
    # Execute
    response = client.get("/analyze/status/non-existent")
    
    # Assert
    assert response.status_code == 404

def test_get_analysis_status_processing(client: TestClient):
    # Setup
    task_id = str(uuid.uuid4())
    _MOCK_REDIS.get.return_value = json.dumps({"status": "processing"})
    
    # Execute
    response = client.get(f"/analyze/status/{task_id}")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"

def test_get_analysis_result_completed(client: TestClient):
    # Setup
    task_id = str(uuid.uuid4())
    result_json = _FAKE_OUTPUT.model_dump_json()
    _MOCK_REDIS.get.return_value = json.dumps({"status": "completed", "result": result_json})
    
    # Execute
    response = client.get(f"/analyze/result/{task_id}")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "identified_components" in data
    assert len(data["identified_components"]) == 1

def test_get_analysis_result_still_processing(client: TestClient):
    # Setup
    task_id = str(uuid.uuid4())
    _MOCK_REDIS.get.return_value = json.dumps({"status": "processing"})
    
    # Execute
    response = client.get(f"/analyze/result/{task_id}")
    
    # Assert
    assert response.status_code == 400
    assert "ainda não foi concluída" in response.json()["detail"]
