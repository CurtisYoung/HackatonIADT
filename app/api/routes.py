from __future__ import annotations
import asyncio
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import ValidationError
import redis

from app.core.redis import get_redis_client
from app.domain.schemas import AIAnalysisOutput, DiagramInput, TaskStatus, SecurityAnalysisOutput
from app.infrastructure.ai_client import AIClient
from app.infrastructure.file_repository import FileOutputRepository
from app.usecases.analyze_diagram import AnalyzeDiagramUseCase
from app.usecases.security_analysis import SecurityAnalysisUseCase

router = APIRouter(prefix="/analyze", tags=["Analysis"])


def _get_redis() -> redis.Redis:
    return get_redis_client()


def _get_ai_client(model_id: Literal["gemini", "bedrock"] = "gemini") -> AIClient:
    """Fábrica do cliente de IA, com suporte a múltiplos provedores."""
    try:
        return AIClient(model_id=model_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Erro de configuração: {exc}")


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


def _run_analysis_in_background(task_id: str, input_data: DiagramInput, redis_client: redis.Redis) -> None:
    """Função executada em background para não bloquear a resposta da API."""
    try:
        client = _get_ai_client(model_id=input_data.model_type)
        repo = _get_repository()
        use_case = AnalyzeDiagramUseCase(ai_client=client, repository=repo)

        result = asyncio.run(use_case.execute(input_data))
        
        task_data = {"status": "completed", "result": result.model_dump_json()}
        redis_client.set(task_id, json.dumps(task_data))

    except Exception as e:
        task_data = {"status": "failed", "error": str(e)}
        redis_client.set(task_id, json.dumps(task_data))


@router.post(
    "/diagram/async",
    response_model=TaskStatus,
    summary="Inicia a análise de um diagrama de forma assíncrona",
    status_code=202,
)
async def analyze_diagram_async(
    input_data: DiagramInput,
    background_tasks: BackgroundTasks,
    redis_client: redis.Redis = Depends(_get_redis),
) -> TaskStatus:
    """
    Recebe um diagrama, inicia a análise em background e retorna um ID de tarefa.
    """
    task_id = str(uuid.uuid4())
    task_data = {"status": "processing"}
    redis_client.set(task_id, json.dumps(task_data))

    background_tasks.add_task(_run_analysis_in_background, task_id, input_data, redis_client)

    return TaskStatus(task_id=task_id, status="processing")


@router.get(
    "/status/{task_id}",
    response_model=TaskStatus,
    summary="Consulta o status de uma análise",
)
async def get_analysis_status(task_id: str, redis_client: redis.Redis = Depends(_get_redis)) -> TaskStatus:
    """Verifica e retorna o status atual de uma tarefa de análise."""
    task_data = redis_client.get(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    
    task = json.loads(task_data)
    return TaskStatus(task_id=task_id, status=task["status"], error=task.get("error"))


@router.get(
    "/result/{task_id}",
    response_model=AIAnalysisOutput,
    summary="Obtém o resultado de uma análise concluída",
)
async def get_analysis_result(task_id: str, redis_client: redis.Redis = Depends(_get_redis)) -> AIAnalysisOutput:
    """Retorna o resultado final de uma análise, se estiver concluída."""
    task_data = redis_client.get(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    task = json.loads(task_data)
    if task["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"A tarefa ainda não foi concluída (status: {task['status']}).",
        )
    return AIAnalysisOutput.model_validate_json(task["result"])


@router.post(
    "/diagram/sync",
    response_model=AIAnalysisOutput,
    summary="Executa a análise de diagrama de forma síncrona",
)
async def analyze_diagram_sync(
    input_data: DiagramInput,
    use_case: AnalyzeDiagramUseCase = Depends(_get_diagram_use_case),
) -> AIAnalysisOutput:
    """
    Mantém o endpoint síncrono original para casos de uso diretos.
    """
    try:
        return await use_case.execute(input_data)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Resposta do modelo inválida: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}")

@router.post(
    "/security/sync",
    response_model=SecurityAnalysisOutput,
    summary="Executa a análise de segurança de forma síncrona",
)
async def analyze_security_sync(
    input_data: DiagramInput,
    use_case: SecurityAnalysisUseCase = Depends(_get_security_use_case),
) -> SecurityAnalysisOutput:
    """
    Endpoint síncrono para análise de segurança.
    """
    try:
        return await use_case.execute(input_data)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Resposta do modelo inválida: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}")
