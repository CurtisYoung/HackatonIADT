from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors as genai_errors
from pydantic import ValidationError

from app.domain.schemas import AIAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import GeminiClient
from app.infrastructure.file_repository import FileOutputRepository
from app.usecases.analyze_diagram import AnalyzeDiagramUseCase

router = APIRouter(prefix="/analyze-diagram", tags=["Analysis"])


def _get_gemini_client() -> GeminiClient:
    """Fábrica do cliente Gemini — cria uma nova instância por requisição."""
    try:
        return GeminiClient()
    except ValueError as exc:
        # Chave de API ausente ou inválida — erro de configuração do servidor.
        raise HTTPException(
            status_code=500,
            detail=f"Erro de configuração da API de IA: {exc}",
        ) from exc


def _get_repository() -> FileOutputRepository:
    """Fábrica do repositório de saída — cria uma nova instância por requisição."""
    return FileOutputRepository()


def _get_use_case(
    ai_client: GeminiClient = Depends(_get_gemini_client),
    repository: FileOutputRepository = Depends(_get_repository),
) -> AnalyzeDiagramUseCase:
    """Fábrica do caso de uso com injeção do cliente de IA e do repositório."""
    return AnalyzeDiagramUseCase(ai_client=ai_client, repository=repository)


@router.post(
    "",
    response_model=AIAnalysisOutput,
    summary="Analyzes an architectural diagram via AI",
    status_code=200,
)
async def analyze_diagram(
    input_data: DiagramInput,
    use_case: AnalyzeDiagramUseCase = Depends(_get_use_case),
) -> AIAnalysisOutput:
    """Recebe um diagrama (base64 ou URL), processa via Gemini Vision e retorna a análise estruturada."""
    try:
        return await use_case.execute(input_data)
    except (genai_errors.ServerError, genai_errors.ClientError) as exc:
        # Todos os modelos falharam — propaga como 503 para o cliente.
        raise HTTPException(
            status_code=503,
            detail=f"Serviço de IA indisponível após todas as tentativas de fallback: {exc}",
        ) from exc
    except ValidationError as exc:
        # Guardrails do Pydantic falharam após todas as tentativas de autocorreção.
        raise HTTPException(
            status_code=500,
            detail=f"Resposta do modelo não passou nos guardrails: {exc}",
        ) from exc
    except Exception as exc:
        # Erro inesperado — registra e retorna 500 genérico.
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar o diagrama: {exc}",
        ) from exc
