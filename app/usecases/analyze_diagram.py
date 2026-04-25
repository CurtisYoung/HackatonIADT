from __future__ import annotations

from app.domain.repositories import OutputRepository
from app.domain.schemas import AIAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import GeminiClient


class AnalyzeDiagramUseCase:
    """Orquestra a análise de um diagrama arquitetural via IA.

    Recebe o cliente de IA e o repositório de saída por injeção de dependência,
    mantendo o caso de uso desacoplado da camada de infraestrutura.
    """

    def __init__(self, ai_client: GeminiClient, repository: OutputRepository) -> None:
        self._ai_client = ai_client
        self._repository = repository

    async def execute(self, input_data: DiagramInput) -> AIAnalysisOutput:
        """Envia o diagrama ao cliente de IA, persiste o resultado e o retorna."""
        result = await self._ai_client.analyze_image(input_data.image_base64)
        await self._repository.save(result)
        return result
