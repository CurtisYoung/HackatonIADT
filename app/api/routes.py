from __future__ import annotations

from fastapi import APIRouter

from app.domain.schemas import AnaliseIAOutput, DiagramaInput
from app.usecases.analisar_diagrama import AnalisarDiagramaUseCase

router = APIRouter(prefix="/analyze-diagram", tags=["Análise de Diagramas"])


def _get_use_case() -> AnalisarDiagramaUseCase:
    """Factory do use case.

    Centraliza a criação (e futura injeção de dependências, ex.: cliente
    Gemini) em um único ponto, mantendo o endpoint limpo.
    """
    return AnalisarDiagramaUseCase()


@router.post(
    "",
    response_model=AnaliseIAOutput,
    summary="Analisa um diagrama arquitetural via IA",
    status_code=200,
)
async def analyze_diagram(entrada: DiagramaInput) -> AnaliseIAOutput:
    """Recebe um diagrama (base64 ou URL) e retorna a análise estruturada."""
    use_case = _get_use_case()
    return await use_case.execute(entrada)
