from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_GENERIC_COMPONENT_TERMS: frozenset[str] = frozenset(
    {
        "box", "arrow", "shape", "element", "item", "object", "figure",
        "line", "circle", "rectangle", "square", "triangle", "oval",
        "caixa", "seta", "forma", "elemento", "item", "objeto",
    }
)
_MIN_RISK_WORDS = 5


class DiagramInput(BaseModel):
    """Payload de entrada para análise, suportando múltiplos tipos e modelos."""
    model_config = ConfigDict(str_strip_whitespace=True)

    image_base64: Optional[str] = None
    file_path: Optional[str] = None
    image_url: Optional[str] = None
    model_type: Literal["gemini", "bedrock"] = "bedrock"

    @model_validator(mode="after")
    def check_at_least_one(self) -> "DiagramInput":
        if not self.image_base64 and not self.file_path and not self.image_url:
            raise ValueError("É necessário fornecer 'image_base64', 'file_path' ou 'image_url'.")
        return self


class TaskStatus(BaseModel):
    """Representa o status de uma tarefa assíncrona."""
    task_id: str
    status: Literal["processing", "completed", "failed"]
    error: Optional[str] = None


class IdentifiedComponent(BaseModel):
    id: str
    name: str
    type: str
    function: str

    @field_validator("name")
    @classmethod
    def components_must_be_technical(cls, name: str) -> str:
        """Componentes não devem ser nomes genéricos de formas."""
        if name.strip().lower() in _GENERIC_COMPONENT_TERMS:
            raise ValueError(
                f"Nome de componente '{name}' é genérico demais. "
                "Use termos técnicos específicos (ex: 'API Gateway', 'PostgreSQL')."
            )
        return name

class ArchitecturalRisk(BaseModel):
    risk: str
    severity: Literal["Critical", "High", "Medium", "Low"]
    impact: str
    affected_components: list[str]

    @field_validator("risk")
    @classmethod
    def risks_must_be_descriptive(cls, risk: str) -> str:
        """O título do risco deve ser minimamente descritivo."""
        if len(risk.split()) < _MIN_RISK_WORDS:
            raise ValueError(
                f"O risco '{risk}' é muito vago. Deve ter pelo menos {_MIN_RISK_WORDS} palavras."
            )
        return risk

class Recommendation(BaseModel):
    action: str
    mitigates_risk: str


class AIAnalysisOutput(BaseModel):
    """Esquema de saída estruturada para a análise da arquitetura."""
    model_config = ConfigDict(frozen=True)

    identified_components: list[IdentifiedComponent]
    architectural_risks: list[ArchitecturalRisk]
    recommendations: list[Recommendation]
    uncertainties: list[str] = []


class SecurityAnalysisOutput(BaseModel):
    """Esquema de saída para a análise de segurança."""
    security_recommendations: list[str]
