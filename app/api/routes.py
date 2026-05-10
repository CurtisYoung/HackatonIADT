from __future__ import annotations
import os
import json
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header
from pydantic import ValidationError
import redis

from app.core.redis import get_redis_client
from app.domain.schemas import AIAnalysisOutput, DiagramInput, TaskStatus, SecurityAnalysisOutput
from app.infrastructure.ai_client import AIClient
from app.infrastructure.file_repository import FileOutputRepository
from app.usecases.analyze_diagram import AnalyzeDiagramUseCase
from app.usecases.security_analysis import SecurityAnalysisUseCase

# ---------- Dependências ----------

def _get_redis() -> redis.Redis:
    return get_redis_client()


def _get_ai_client(model_id: Literal["gemini", "bedrock"] = "gemini") -> AIClient:
    """Fábrica do cliente de IA, com suporte a múltiplos provedores."""
    try:
        return AIClient(model_id=model_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Erro de configuração: {exc}")


_get_gemini_client = _get_ai_client  # Alias para compatibilidade com testes


def _get_repository() -> FileOutputRepository:
    return FileOutputRepository()


def _get_diagram_use_case(
    client: AIClient = Depends(_get_ai_client),
    repo: FileOutputRepository = Depends(_get_repository),
) -> AnalyzeDiagramUseCase:
    return AnalyzeDiagramUseCase(ai_client=client, repository=repo)


def _get_security_use_case(
    client: AIClient = Depends(_get_ai_client),
    repo: FileOutputRepository = Depends(_get_repository),
) -> SecurityAnalysisUseCase:
    return SecurityAnalysisUseCase(ai_client=client, repository=repo)

router = APIRouter(tags=["Analysis"], dependencies=[])  # dependencies will be filled later

# ---------- Segurança via API Key ----------
API_KEY = os.getenv("API_KEY") or "default-secret-key"

def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")

# Aplica a dependência a todos os endpoints do router
router.dependencies.append(Depends(verify_api_key))

# ---------- Health Check ----------
@router.get("/health", summary="Endpoint de saúde", response_model=dict)
async def health_check() -> dict:
    """Retorna o status de saúde da aplicação, verificando conexões críticas."""
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"
    return {"status": "ok", "redis": redis_status}

@router.post(
    "/analyze/diagram/async",
    response_model=TaskStatus,
    summary="Inicia a análise de um diagrama de forma assíncrona",
    status_code=202,
)
async def analyze_diagram_async(
    input_data: DiagramInput,
    background_tasks: BackgroundTasks,
    redis_client: redis.Redis = Depends(_get_redis),
) -> TaskStatus:
    """Recebe um diagrama, inicia a análise em background e retorna um ID de tarefa."""
    task_id = str(uuid.uuid4())
    redis_client.set(task_id, json.dumps({"status": "processing"}))
    background_tasks.add_task(_run_analysis_in_background, task_id, input_data, redis_client)
    return TaskStatus(task_id=task_id, status="processing")

# ---------- Rotas existentes (mantidas) ----------

async def _run_analysis_in_background(task_id: str, input_data: DiagramInput, redis_client: redis.Redis) -> None:
    """Função executada em background para não bloquear a resposta da API."""
    try:
        client = _get_ai_client(model_id=input_data.model_type)
        repo = _get_repository()
        use_case = AnalyzeDiagramUseCase(ai_client=client, repository=repo)

        result = await use_case.execute(input_data)

        task_data = {"status": "completed", "result": result.model_dump_json()}
        redis_client.set(task_id, json.dumps(task_data))

    except Exception as e:
        task_data = {"status": "failed", "error": str(e)}
        redis_client.set(task_id, json.dumps(task_data))


@router.post(
    "/analyze/security/sync",
    response_model=SecurityAnalysisOutput,
    summary="Executa a análise de segurança de forma síncrona",
)
async def analyze_security_sync(
    input_data: DiagramInput,
    use_case: SecurityAnalysisUseCase = Depends(_get_security_use_case),
) -> SecurityAnalysisOutput:
    """Endpoint síncrono para análise de segurança."""
    try:
        return await use_case.execute(input_data)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Resposta do modelo inválida: {exc}")
    except Exception as exc:
        status_code = getattr(exc, "status_code", getattr(exc, "code", 500))
        if not isinstance(status_code, int) or status_code < 400 or status_code > 599:
            status_code = 500
        raise HTTPException(status_code=status_code, detail=f"Erro na análise: {exc}")