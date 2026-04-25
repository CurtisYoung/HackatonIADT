from __future__ import annotations

from app.domain.schemas import AIAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import GeminiClient


class AnalyzeDiagramUseCase:
    """Orchestrates the analysis of an architectural diagram via AI.

    Receives the AI client through dependency injection, keeping
    the use case decoupled from the infrastructure.
    """

    def __init__(self, ai_client: GeminiClient) -> None:
        self._ai_client = ai_client

    async def execute(self, input_data: DiagramInput) -> AIAnalysisOutput:
        """Sends the diagram to the AI client and returns the validated analysis."""
        return await self._ai_client.analyze_image(input_data.image_base64)
