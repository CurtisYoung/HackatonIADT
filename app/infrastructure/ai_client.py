from __future__ import annotations
import base64
import os
from typing import Literal
import litellm
from pydantic import BaseModel
from dotenv import load_dotenv
from app.core.logging import get_logger
from app.domain.schemas import AIAnalysisOutput, SecurityAnalysisOutput

load_dotenv()
log = get_logger(__name__)

_SYSTEM_PROMPT = """## ROLE
You are a Senior Software Architect and Cloud Infrastructure Auditor. Your task is to perform a rigorous structural and security audit of the provided architecture diagram.

## TASK
1. VISUAL CATALOGING: Identify every node, service, database, and networking boundary explicitly labeled or iconographically recognizable.
2. RISK ANALYSIS: Identify Single Points of Failure (SPOF), security vulnerabilities (e.g., exposed databases), resilience gaps, and scalability bottlenecks.
3. MITIGATION: Provide actionable recommendations based on Well-Architected Frameworks.

## CONSTRAINTS
- Output MUST be a valid JSON object.
- Be precise: Reference specific component names in your risk analysis.
- Risk titles MUST be descriptive and have at least 5 words.
- If an element is blurry or its function is unclear, list it under "uncertainties" rather than guessing.
- Keep descriptions concise, technical, and objective.

## OUTPUT FORMAT
{
  "identified_components": [
    {
      "id": "c1",
      "name": "Component Name",
      "type": "Service/Resource Type",
      "function": "Brief technical purpose"
    }
  ],
  "architectural_risks": [
    {
      "risk": "Technical title",
      "severity": "Critical/High/Medium/Low",
      "impact": "What happens if this fails (concise)",
      "affected_components": ["c1"]
    }
  ],
  "recommendations": [
    {
      "action": "Concrete mitigation step",
      "mitigates_risk": "Reference the risk title"
    }
  ],
  "uncertainties": ["List any ambiguous or unidentifiable elements"]
}
"""

_SECURITY_SYSTEM_PROMPT = """## ROLE
You are a Senior Security Analyst. Your task is to perform a security audit of the provided architecture diagram.

## TASK
1. Analyze the provided architecture diagram for security vulnerabilities.
2. Provide a list of security recommendations as bullet points.

## CONSTRAINTS
- Output MUST be a valid JSON object.
- Provide at least 3 security recommendations.
- Each recommendation should be a clear and actionable bullet point.

## OUTPUT FORMAT
{
  "security_recommendations": [
    "Bullet point 1",
    "Bullet point 2",
    "Bullet point 3"
  ]
}
"""

SUPPORTED_MODELS = {
    "gemini": "gemini/gemini-2.5-flash",
    "bedrock": "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
}

class AIClient:
    """Cliente agnóstico de provedor de IA, usando LiteLLM para análise de imagens."""

    def __init__(self, model_id: Literal["gemini", "bedrock"] = "gemini") -> None:
        self.model_name = SUPPORTED_MODELS.get(model_id)
        if not self.model_name:
            raise ValueError(f"Modelo '{model_id}' não é suportado.")

        if "gemini" in self.model_name and not os.environ.get("GEMINI_API_KEY"):
            raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")
        if "bedrock" in self.model_name and not (
            os.environ.get("AWS_ACCESS_KEY_ID") and
            os.environ.get("AWS_SECRET_ACCESS_KEY") and
            os.environ.get("AWS_REGION_NAME")
        ):
            raise ValueError("As variáveis de ambiente da AWS para o Bedrock não foram definidas.")

    async def _analyze(self, base64_str: str, system_prompt: str, output_schema: BaseModel) -> BaseModel:
        """Envia a imagem para o modelo de IA e retorna a análise estruturada."""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_str}"
                        },
                    },
                ],
            }
        ]

        try:
            log.info(f"Chamando API via LiteLLM com o modelo: {self.model_name}")
            response = await litellm.acompletion(
                model=self.model_name,
                messages=messages,
                response_format={"type": "json_object"},
            )
            
            response_content = response.choices[0].message.content
            
            return output_schema.model_validate_json(response_content)

        except Exception as e:
            log.error(f"Erro na chamada LiteLLM: {e}", exc_info=True)
            raise

    async def analyze_image(self, base64_str: str) -> AIAnalysisOutput:
        return await self._analyze(base64_str, _SYSTEM_PROMPT, AIAnalysisOutput)

    async def analyze_security(self, base64_str: str) -> SecurityAnalysisOutput:
        return await self._analyze(base64_str, _SECURITY_SYSTEM_PROMPT, SecurityAnalysisOutput)
