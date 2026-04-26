from __future__ import annotations

import base64
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from google.genai import errors as genai_errors

from app.domain.repositories import OutputRepository
from app.domain.schemas import AIAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import (
    GeminiClient,
    _FALLBACK_MODEL,
    _PRIMARY_MODEL,
)
from app.infrastructure.file_repository import FileOutputRepository
from app.usecases.analyze_diagram import AnalyzeDiagramUseCase

# Sample architecture diagram shipped with the project.
_ARCHITECTURE_PNG = Path(__file__).parent.parent / "architecture.png"


def _load_image_base64() -> str:
    return base64.b64encode(_ARCHITECTURE_PNG.read_bytes()).decode()


def _mock_repository() -> AsyncMock:
    """Retorna um AsyncMock que satisfaz a interface OutputRepository."""
    mock = AsyncMock(spec=OutputRepository)
    mock.save.return_value = None
    return mock


@pytest.mark.asyncio
async def test_analyze_diagram_usecase_returns_expected_output() -> None:
    """Teste de integração: o caso de uso deve chamar o GeminiClient real e retornar
    um AIAnalysisOutput válido que passe em todos os guardrails do Pydantic.

    Requer que GEMINI_API_KEY esteja definida (via .env ou variável de ambiente).
    O repositório grava em diretório temporário para evitar arquivos em data/outputs/.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set — skipping real API integration test")

    if not _ARCHITECTURE_PNG.exists():
        pytest.skip("architecture.png not found in project root")

    input_data = DiagramInput(image_base64=_load_image_base64())
    use_case = AnalyzeDiagramUseCase(
        ai_client=GeminiClient(),
        repository=_mock_repository(),
    )
    result = await use_case.execute(input_data)

    assert isinstance(result, AIAnalysisOutput)
    assert isinstance(result.identified_components, list)
    assert len(result.identified_components) > 0
    assert isinstance(result.architectural_risks, list)
    assert len(result.architectural_risks) > 0
    assert isinstance(result.recommendations, list)
    assert len(result.recommendations) > 0

    for risk in result.architectural_risks:
        assert len(risk) <= 300, f"Risk exceeds 300 characters: {risk!r}"


@pytest.mark.asyncio
async def test_usecase_calls_repository_save() -> None:
    """O caso de uso deve chamar repository.save() exatamente uma vez com o resultado da IA."""
    fake_result = AIAnalysisOutput(
        identified_components=["API Gateway", "Load Balancer"],
        architectural_risks=[
            "Single point of failure in the API gateway causes total service outage during peak load."
        ],
        recommendations=["Add a secondary gateway instance with health checks."],
    )

    mock_ai = AsyncMock()
    mock_ai.analyze_image.return_value = fake_result
    mock_repo = _mock_repository()

    use_case = AnalyzeDiagramUseCase(ai_client=mock_ai, repository=mock_repo)
    input_data = DiagramInput(image_base64="aW1hZ2VtX2Zha2VfYmFzZTY0")

    result = await use_case.execute(input_data)

    mock_repo.save.assert_awaited_once_with(fake_result)
    assert result == fake_result


@pytest.mark.asyncio
async def test_file_repository_saves_json(tmp_path: Path) -> None:
    """FileOutputRepository deve criar um arquivo JSON no diretório de saída configurado."""
    repo = FileOutputRepository(output_dir=tmp_path)
    analysis = AIAnalysisOutput(
        identified_components=["Database", "Cache"],
        architectural_risks=[
            "No replication on the database layer means data loss on instance failure."
        ],
        recommendations=["Enable multi-AZ replication for the primary database."],
    )

    await repo.save(analysis)

    saved_files = list(tmp_path.glob("analysis_*.json"))
    assert len(saved_files) == 1, "Expected exactly one output file"

    content = saved_files[0].read_text(encoding="utf-8")
    assert "Database" in content
    assert "Cache" in content


def test_aianalysisoutput_rejects_vague_risk() -> None:
    """Guardrail: architectural_risks com menos de 10 palavras deve disparar ValidationError.

    Simula uma resposta genérica/alucinada do LLM como 'Security risk' e verifica
    que o modelo Pydantic aplica o guardrail de mínimo de palavras.
    """
    with pytest.raises(ValidationError) as exc_info:
        AIAnalysisOutput(
            identified_components=["API Gateway", "Load Balancer"],
            architectural_risks=["Security risk."],  # only 2 words — must fail
            recommendations=["Improve security posture."],
        )

    errors = exc_info.value.errors()
    assert any(
        "at least 10 words" in str(e.get("msg", "")) for e in errors
    ), f"Expected minimum-word error, got: {errors}"


def test_aianalysisoutput_rejects_generic_component() -> None:
    """Guardrail: identified_components com nomes genéricos de formas deve disparar ValidationError.

    Termos como 'box' ou 'arrow' indicam que o LLM descreveu elementos visuais
    em vez de componentes arquiteturais reais.
    """
    with pytest.raises(ValidationError) as exc_info:
        AIAnalysisOutput(
            identified_components=["box", "arrow"],  # generic — must fail
            architectural_risks=[
                "No authentication layer exposes all internal services to the public internet."
            ],
            recommendations=["Add an authentication gateway."],
        )

    errors = exc_info.value.errors()
    assert any(
        "too generic" in str(e.get("msg", "")) for e in errors
    ), f"Expected generic-component error, got: {errors}"


@pytest.mark.asyncio
async def test_gemini_client_falls_back_on_retriable_error() -> None:
    """GeminiClient deve trocar automaticamente para o modelo de fallback quando o
    principal falha com erro HTTP retriável (429, 500, 503 ou 504).

    Verifica que:
    - O modelo principal é chamado primeiro.
    - Em caso de erro retriável, o modelo de fallback é utilizado.
    - O resultado final do fallback é retornado corretamente.
    """
    fake_result = AIAnalysisOutput(
        identified_components=["API Gateway", "Load Balancer"],
        architectural_risks=[
            "Single point of failure in the API gateway causes total service outage during peak load."
        ],
        recommendations=["Add a secondary gateway instance with health checks."],
    )

    models_called: list[str] = []

    def _mock_retries(model: str, contents: list) -> AIAnalysisOutput:
        models_called.append(model)
        if model == _PRIMARY_MODEL:
            # Simula sobrecarga 503 no modelo principal.
            err = genai_errors.ServerError.__new__(genai_errors.ServerError)
            err.code = 503
            raise err
        return fake_result

    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}):
        client = GeminiClient()
        client._call_with_guardrail_retries = _mock_retries  # type: ignore[method-assign]
        result = await client.analyze_image(base64.b64encode(b"fake-image").decode())

    assert result == fake_result
    assert models_called == [_PRIMARY_MODEL, _FALLBACK_MODEL], (
        f"Expected [{_PRIMARY_MODEL!r}, {_FALLBACK_MODEL!r}], got {models_called}"
    )
