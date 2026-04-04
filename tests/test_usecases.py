from __future__ import annotations

import pytest

from app.domain.schemas import AnaliseIAOutput, DiagramaInput
from app.usecases.analisar_diagrama import AnalisarDiagramaUseCase


@pytest.mark.asyncio
async def test_analisar_diagrama_usecase_retorna_output_esperado() -> None:
    """O use case deve retornar uma instância válida de AnaliseIAOutput
    quando recebe um DiagramaInput com imagem_base64 preenchida."""
    entrada = DiagramaInput(imagem_base64="aW1hZ2VtX2Zha2VfYmFzZTY0")

    use_case = AnalisarDiagramaUseCase()
    resultado = await use_case.execute(entrada)

    assert isinstance(resultado, AnaliseIAOutput)
    assert isinstance(resultado.componentes_identificados, list)
    assert len(resultado.componentes_identificados) > 0
    assert isinstance(resultado.riscos_arquiteturais, list)
    assert len(resultado.riscos_arquiteturais) > 0
    assert isinstance(resultado.recomendacoes, list)
    assert len(resultado.recomendacoes) > 0

    # Garante que a validação de tamanho máximo por item está sendo respeitada
    for risco in resultado.riscos_arquiteturais:
        assert len(risco) <= 300, f"Risco excede 300 caracteres: {risco!r}"
