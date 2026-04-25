from __future__ import annotations

from fastapi import APIRouter, Depends

from app.domain.schemas import AIAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import GeminiClient
from app.usecases.analyze_diagram import AnalyzeDiagramUseCase

router = APIRouter(prefix="/analyze-diagram", tags=["Diagram Analysis"])


def _get_gemini_client() -> GeminiClient:
    """Gemini client factory (one per request)."""
    return GeminiClient()


def _get_use_case(
    ai_client: GeminiClient = Depends(_get_gemini_client),
) -> AnalyzeDiagramUseCase:
    """Use case factory with AI client injection."""
    return AnalyzeDiagramUseCase(ai_client=ai_client)


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
    """Receives a diagram (base64 or URL) and returns the structured analysis."""
    return await use_case.execute(input_data)
