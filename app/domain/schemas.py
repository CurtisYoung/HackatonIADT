from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class DiagramaInput(BaseModel):
    """Payload de entrada do endpoint de análise de diagrama."""

    model_config = ConfigDict(str_strip_whitespace=True)

    imagem_base64: str
    url: Optional[str] = None


class AnaliseIAOutput(BaseModel):
    """Schema de saída estruturada exigida do LLM via Gemini Vision."""

    model_config = ConfigDict(frozen=True)

    componentes_identificados: list[str]
    riscos_arquiteturais: list[Annotated[str, Field(max_length=300)]]
    recomendacoes: list[str]
