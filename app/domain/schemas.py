from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Termos genéricos e não-técnicos que indicam que o LLM descreveu formas visuais
# do diagrama em vez dos componentes arquiteturais reais.
_GENERIC_COMPONENT_TERMS: frozenset[str] = frozenset(
    {
        "box", "arrow", "shape", "element", "item", "object", "figure",
        "line", "circle", "rectangle", "square", "triangle", "oval",
        # Variantes em português (proteção contra respostas mistas de idioma)
        "caixa", "seta", "forma", "elemento", "item", "objeto",
    }
)

_MIN_RISK_WORDS = 10


class DiagramInput(BaseModel):
    """Payload de entrada para o endpoint de análise de diagramas."""

    model_config = ConfigDict(str_strip_whitespace=True)

    image_base64: str
    url: Optional[str] = None


class AIAnalysisOutput(BaseModel):
    """Esquema de saída estruturada exigido do LLM via Gemini Vision."""

    model_config = ConfigDict(frozen=True)

    identified_components: list[str]
    architectural_risks: list[Annotated[str, Field(max_length=300)]]
    recommendations: list[str]

    @field_validator("architectural_risks", mode="before")
    @classmethod
    def risks_must_be_descriptive(cls, risks: list) -> list:
        """Guardrail: cada risco deve conter pelo menos 10 palavras.

        Entradas curtas como 'Security risk' ou 'Performance issue' são vagas
        demais para serem acionáveis e provavelmente indicam respostas alucinadas.
        """
        for risk in risks:
            word_count = len(str(risk).split())
            if word_count < _MIN_RISK_WORDS:
                raise ValueError(
                    f"Architectural risk is too vague ({word_count} words). "
                    f"Each risk must have at least {_MIN_RISK_WORDS} words "
                    f"to be considered actionable. Got: {risk!r}"
                )
        return risks

    @field_validator("identified_components", mode="before")
    @classmethod
    def components_must_be_technical(cls, components: list) -> list:
        """Guardrail: componentes identificados não devem ser nomes genéricos de formas.

        Termos como 'box' ou 'arrow' indicam que o LLM descreveu os elementos visuais
        do diagrama em vez dos componentes arquiteturais reais.
        """
        for component in components:
            normalized = str(component).strip().lower()
            if normalized in _GENERIC_COMPONENT_TERMS:
                raise ValueError(
                    f"Component name {component!r} is too generic. "
                    "Use specific technical terms (e.g. 'API Gateway', "
                    "'Load Balancer', 'PostgreSQL Database')."
                )
        return components
