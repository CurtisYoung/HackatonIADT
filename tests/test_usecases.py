from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.domain.schemas import AIAnalysisOutput, DiagramInput
from app.usecases.analyze_diagram import AnalyzeDiagramUseCase

_FAKE_OUTPUT = AIAnalysisOutput(
    identified_components=["API Gateway", "Database"],
    architectural_risks=["Single point of failure in the gateway."],
    recommendations=["Add redundancy to the gateway."],
)


@pytest.mark.asyncio
async def test_analyze_diagram_usecase_returns_expected_output() -> None:
    """The use case should return a valid AIAnalysisOutput instance
    when given a DiagramInput with image_base64 filled in."""
    input_data = DiagramInput(image_base64="aW1hZ2VtX2Zha2VfYmFzZTY0")

    mock_client = AsyncMock()
    mock_client.analyze_image.return_value = _FAKE_OUTPUT

    use_case = AnalyzeDiagramUseCase(ai_client=mock_client)
    result = await use_case.execute(input_data)

    mock_client.analyze_image.assert_awaited_once_with(input_data.image_base64)
    assert isinstance(result, AIAnalysisOutput)
    assert isinstance(result.identified_components, list)
    assert len(result.identified_components) > 0
    assert isinstance(result.architectural_risks, list)
    assert len(result.architectural_risks) > 0
    assert isinstance(result.recommendations, list)
    assert len(result.recommendations) > 0

    for risk in result.architectural_risks:
        assert len(risk) <= 300, f"Risk exceeds 300 characters: {risk!r}"
