from __future__ import annotations
import os
import json
import uuid
from typing import Literal, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, UploadFile, File, Form, Request
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


def _get_ai_client(model_id: Literal["gemini", "bedrock"] = "bedrock") -> AIClient:
    """Fábrica do cliente de IA, com suporte a múltiplos provedores."""
    try:
        return AIClient(model_id=model_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Erro de configuração: {exc}")


def _get_ai_client_factory() -> Callable:
    return _get_ai_client


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

# ---------- Rotas principais ----------

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
    """
    Recebe um diagrama, inicia a análise em background e retorna um ID de tarefa.
    """
    task_id = str(uuid.uuid4())
    task_data = {"status": "processing"}
    redis_client.set(task_id, json.dumps(task_data))

    background_tasks.add_task(_run_analysis_in_background, task_id, input_data, redis_client)

    return TaskStatus(task_id=task_id, status="processing")


@router.get(
    "/analyze/status/{task_id}",
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
    "/analyze/result/{task_id}",
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
    "/analyze/diagram/upload",
    response_model=AIAnalysisOutput,
    summary="Executa a análise de diagrama fazendo upload do arquivo (ideal para arquivos grandes)",
)
async def analyze_diagram_upload(
    request: Request,
    file: UploadFile = File(...),
    model_type: Literal["gemini", "bedrock"] = Form("bedrock"),
    repo: FileOutputRepository = Depends(_get_repository),
    ai_factory: Callable = Depends(_get_ai_client_factory),
) -> AIAnalysisOutput:
    """
    Recebe um arquivo (multipart/form-data), salva temporariamente, gera uma URL,
    e o processa. Ideal para clientes que não suportam Base64 grande.
    """
    import shutil
    import uuid
    from pathlib import Path

    try:
        file_id = f"{uuid.uuid4()}-{file.filename}"
        upload_path = Path("data/uploads") / file_id

        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        base_url = str(request.base_url).rstrip("/")
        image_url = f"{base_url}/uploads/{file_id}"

        input_data = DiagramInput(
            image_url=image_url,
            model_type=model_type
        )

        client = ai_factory(model_id=model_type)
        use_case = AnalyzeDiagramUseCase(ai_client=client, repository=repo)
        return await use_case.execute(input_data)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Resposta do modelo inválida: {exc}")
    except Exception as exc:
        status_code = getattr(exc, "status_code", getattr(exc, "code", 500))
        if not isinstance(status_code, int) or status_code < 400 or status_code > 599:
            status_code = 500
        raise HTTPException(status_code=status_code, detail=f"Erro na análise: {exc}")


@router.post(
    "/analyze/diagram/sync",
    response_model=AIAnalysisOutput,
    summary="Executa a análise de diagrama de forma síncrona",
)
@router.post(
    "/analyze-diagram",
    response_model=AIAnalysisOutput,
    include_in_schema=False,
)
async def analyze_diagram_sync(
    input_data: DiagramInput,
    repo: FileOutputRepository = Depends(_get_repository),
    ai_factory: Callable = Depends(_get_ai_client_factory),
) -> AIAnalysisOutput:
    """
    Mantém o endpoint síncrono original para casos de uso diretos.
    """
    try:
        client = ai_factory(model_id=input_data.model_type)
        use_case = AnalyzeDiagramUseCase(ai_client=client, repository=repo)
        return await use_case.execute(input_data)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Resposta do modelo inválida: {exc}")
    except Exception as exc:
        # Tenta extrair código de status se disponível (ex: de erros do SDK)
        status_code = getattr(exc, "status_code", getattr(exc, "code", 500))
        if not isinstance(status_code, int) or status_code < 400 or status_code > 599:
            status_code = 500
        raise HTTPException(status_code=status_code, detail=f"Erro na análise: {exc}")


@router.post(
    "/analyze/security/sync",
    response_model=SecurityAnalysisOutput,
    summary="Executa a análise de segurança de forma síncrona",
)
async def analyze_security_sync(
    input_data: DiagramInput,
    repo: FileOutputRepository = Depends(_get_repository),
    ai_factory: Callable = Depends(_get_ai_client_factory),
) -> SecurityAnalysisOutput:
    """
    Endpoint síncrono para análise de segurança.
    """
    try:
        client = ai_factory(model_id=input_data.model_type)
        use_case = SecurityAnalysisUseCase(ai_client=client, repository=repo)
        return await use_case.execute(input_data)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Resposta do modelo inválida: {exc}")
    except Exception as exc:
        # Tenta extrair código de status se disponível (ex: de erros do SDK)
        status_code = getattr(exc, "status_code", getattr(exc, "code", 500))
        if not isinstance(status_code, int) or status_code < 400 or status_code > 599:
            status_code = 500
        raise HTTPException(status_code=status_code, detail=f"Erro na análise: {exc}")