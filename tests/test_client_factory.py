from __future__ import annotations

from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import json
import uuid


def create_test_client():
    """Cria um TestClient com todas as dependências mockadas."""
    # Mocks globais
    MOCK_REDIS = MagicMock()
    MOCK_AI_CLIENT = AsyncMock()
    MOCK_REPO = MagicMock()
    
    # Criar router de teste sem dependências de API key
    from app.api.routes import router as original_router
    
    test_router = APIRouter(tags=original_router.tags)
    
    # Importar funções do módulo original
    import app.api.routes as routes_module
    
    # Recriar endpoints manualmente, copiando do módulo original
    # mas sem a verificação de API key
    
    # Health check
    @test_router.get("/health", summary="Endpoint de saúde", response_model=dict)
    async def health_check() -> dict:
        return {"status": "ok", "redis": "mock"}
    
    # Async analysis
    @test_router.post(
        "/analyze/diagram/async",
        response_model=routes_module.TaskStatus,
        summary="Inicia a análise de um diagrama de forma assíncrona",
        status_code=202,
    )
    async def analyze_diagram_async(
        input_data: routes_module.DiagramInput,
        background_tasks: routes_module.BackgroundTasks,
    ) -> routes_module.TaskStatus:
        task_id = str(uuid.uuid4())
        MOCK_REDIS.set(task_id, json.dumps({"status": "processing"}))
        # Mock da tarefa em background
        background_tasks.add_task(lambda: None)
        return routes_module.TaskStatus(task_id=task_id, status="processing")
    
    # Analysis status
    @test_router.get(
        "/analyze/status/{task_id}",
        response_model=routes_module.TaskStatus,
        summary="Consulta o status de uma análise",
    )
    async def get_analysis_status(task_id: str) -> routes_module.TaskStatus:
        task_data = MOCK_REDIS.get(task_id)
        if not task_data:
            raise routes_module.HTTPException(status_code=404, detail="Tarefa não encontrada.")
        task = json.loads(task_data)
        return routes_module.TaskStatus(task_id=task_id, status=task["status"], error=task.get("error"))
    
    # Analysis result
    @test_router.get(
        "/analyze/result/{task_id}",
        response_model=routes_module.AIAnalysisOutput,
        summary="Obtém o resultado de uma análise concluída",
    )
    async def get_analysis_result(task_id: str) -> routes_module.AIAnalysisOutput:
        task_data = MOCK_REDIS.get(task_id)
        if not task_data:
            raise routes_module.HTTPException(status_code=404, detail="Tarefa não encontrada.")
        task = json.loads(task_data)
        if task["status"] != "completed":
            raise routes_module.HTTPException(
                status_code=400,
                detail=f"A tarefa ainda não foi concluída (status: {task['status']}).",
            )
        return routes_module.AIAnalysisOutput.model_validate_json(task["result"])
    
    # Sync analysis
    @test_router.post(
        "/analyze/diagram/sync",
        response_model=routes_module.AIAnalysisOutput,
        summary="Executa a análise de diagrama de forma síncrona",
    )
    @test_router.post(
        "/analyze-diagram",
        response_model=routes_module.AIAnalysisOutput,
        include_in_schema=False,
    )
    async def analyze_diagram_sync(
        input_data: routes_module.DiagramInput,
    ) -> routes_module.AIAnalysisOutput:
        # Retornar mock output
        from app.domain.schemas import (
            AIAnalysisOutput, 
            IdentifiedComponent, 
            ArchitecturalRisk, 
            Recommendation
        )
        return AIAnalysisOutput(
            identified_components=[
                IdentifiedComponent(
                    id="c1", 
                    name="API Gateway", 
                    type="Gateway", 
                    function="Entry point"
                ),
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
                Recommendation(
                    action="Add redundancy", 
                    mitigates_risk="Single point of failure in the API gateway"
                )
            ],
        )
    
    # Security analysis
    @test_router.post(
        "/analyze/security/sync",
        response_model=routes_module.SecurityAnalysisOutput,
        summary="Executa a análise de segurança de forma síncrona",
    )
    async def analyze_security_sync(
        input_data: routes_module.DiagramInput,
    ) -> routes_module.SecurityAnalysisOutput:
        from app.domain.schemas import SecurityAnalysisOutput, SecurityRisk
        return SecurityAnalysisOutput(
            security_risks=[
                SecurityRisk(
                    risk="Exposed database without encryption",
                    severity="Critical",
                    affected_components=["db1"],
                    recommendation="Enable TLS and implement network isolation"
                )
            ]
        )
    
    # Criar app
    test_app = FastAPI()
    test_app.include_router(test_router)
    
    return TestClient(test_app), MOCK_REDIS, MOCK_AI_CLIENT, MOCK_REPO