from __future__ import annotations

import base64
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.domain.repositories import OutputRepository
from app.domain.schemas import (
    AIAnalysisOutput,
    ArchitecturalRisk,
    DiagramInput,
    IdentifiedComponent,
    Recommendation,
)
from app.infrastructure.ai_client import AIClient
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
        ai_client=AIClient(),
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
        assert len(risk.risk) <= 300, f"Risk exceeds 300 characters: {risk!r}"


@pytest.mark.asyncio
async def test_usecase_calls_repository_save() -> None:
    """O caso de uso deve chamar repository.save() exatamente uma vez com o resultado da IA."""
    fake_result = AIAnalysisOutput(
        identified_components=[
            IdentifiedComponent(id="c1", name="API Gateway", type="Gateway", function="Entry point"),
            IdentifiedComponent(id="c2", name="Load Balancer", type="LB", function="Traffic distribution"),
        ],
        architectural_risks=[
            ArchitecturalRisk(
                risk="Single point of failure in the API gateway causes total service outage during peak load.",
                severity="Critical",
                impact="Total service outage",
                affected_components=["c1"],
            )
        ],
        recommendations=[
            Recommendation(
                action="Add a secondary gateway instance with health checks.",
                mitigates_risk="Single point of failure in the API gateway causes total service outage during peak load.",
            )
        ],
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
        identified_components=[
            IdentifiedComponent(id="c1", name="Database", type="Database", function="Data storage"),
            IdentifiedComponent(id="c2", name="Cache", type="Cache", function="Performance layer"),
        ],
        architectural_risks=[
            ArchitecturalRisk(
                risk="No replication on the database layer means data loss on instance failure.",
                severity="Critical",
                impact="Data loss on instance failure",
                affected_components=["c1"],
            )
        ],
        recommendations=[
            Recommendation(
                action="Enable multi-AZ replication for the primary database.",
                mitigates_risk="No replication on the database layer means data loss on instance failure.",
            )
        ],
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
            identified_components=[
                IdentifiedComponent(id="c1", name="API Gateway", type="Gateway", function="Entry"),
                IdentifiedComponent(id="c2", name="Load Balancer", type="LB", function="Distribution"),
            ],
            architectural_risks=[
                ArchitecturalRisk(
                    risk="Security risk.",
                    severity="High",
                    impact="Unknown",
                    affected_components=["c1"],
                )
            ],
            recommendations=[
                Recommendation(action="Improve security posture.", mitigates_risk="Security risk.")
            ],
        )

    errors = exc_info.value.errors()
    assert any(
        "pelo menos 5 palavras" in str(e.get("msg", "")) for e in errors
    ), f"Expected minimum-word error, got: {errors}"


def test_aianalysisoutput_rejects_generic_component() -> None:
    """Guardrail: identified_components com nomes genéricos de formas deve disparar ValidationError.

    Termos como 'box' ou 'arrow' indicam que o LLM descreveu elementos visuais
    em vez de componentes arquiteturais reais.
    """
    with pytest.raises(ValidationError) as exc_info:
        AIAnalysisOutput(
            identified_components=[
                IdentifiedComponent(id="c1", name="box", type="Shape", function="Visual"),
                IdentifiedComponent(id="c2", name="arrow", type="Shape", function="Visual"),
            ],
            architectural_risks=[
                ArchitecturalRisk(
                    risk="No authentication layer exposes all internal services to the public internet.",
                    severity="Critical",
                    impact="Data breach",
                    affected_components=["c1"],
                )
            ],
            recommendations=[
                Recommendation(
                    action="Add an authentication gateway.",
                    mitigates_risk="No authentication layer exposes all internal services to the public internet.",
                )
            ],
        )

    errors = exc_info.value.errors()
    assert any(
        "genérico demais" in str(e.get("msg", "")) for e in errors
    ), f"Expected generic-component error, got: {errors}"


@pytest.mark.asyncio
async def test_ai_client_model_id_gemini() -> None:
    """AIClient com model_id='gemini' deve ser criado sem erro e expor o model_id."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set — skipping real API integration test")

    client = AIClient(model_id="gemini")
    assert client.model_id == "gemini"

    fake_image = base64.b64encode(b"fake-image").decode()
    result = await client.analyze_image(fake_image)

    assert isinstance(result, AIAnalysisOutput)
    assert isinstance(result.identified_components, list)
