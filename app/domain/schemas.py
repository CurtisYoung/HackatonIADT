from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class DiagramInput(BaseModel):
    """Input payload for the diagram analysis endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True)

    image_base64: str
    url: Optional[str] = None


class AIAnalysisOutput(BaseModel):
    """Structured output schema required from the LLM via Gemini Vision."""

    model_config = ConfigDict(frozen=True)

    identified_components: list[str]
    architectural_risks: list[Annotated[str, Field(max_length=300)]]
    recommendations: list[str]
