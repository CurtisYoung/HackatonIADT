from __future__ import annotations

import base64
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.domain.schemas import AIAnalysisOutput

load_dotenv()  # rede de segurança: garante que o .env seja carregado independentemente do ponto de entrada

_SYSTEM_PROMPT = (
    "You are a Senior Software Architect and Architecture Auditor. "
    "Analyze the architecture diagram provided in the image and extract:\n"
    "1. **identified_components** — list of all components, "
    "services, and resources visible in the diagram.\n"
    "2. **architectural_risks** — list of risks, resilience failures, "
    "single points of failure, and security issues identified "
    "(each item with a maximum of 300 characters).\n"
    "3. **recommendations** — list of concrete actions to mitigate "
    "the identified risks.\n"
    "Respond EXCLUSIVELY in the requested JSON format."
)

_PRIMARY_MODEL = "gemini-2.5-flash"
_FALLBACK_MODEL = "gemini-1.5-flash-8b"
# Códigos HTTP que acionam o fallback automático de modelo (sobrecarga, erro de servidor, rate limit, timeout).
_FALLBACK_ON_CODES = frozenset({429, 500, 503, 504})
_MAX_RETRIES = 2


class GeminiClient:
    """Encapsula a chamada à Gemini Vision via google-genai com saídas estruturadas nativas."""

    def __init__(self, model_name: str = _PRIMARY_MODEL) -> None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "The GEMINI_API_KEY environment variable is not set. "
                "Add it to your .env file or export it before running."
            )
        self._model_name = model_name
        self._client = genai.Client(api_key=api_key)

    async def analyze_image(self, base64_str: str) -> AIAnalysisOutput:
        """Envia a imagem (base64) ao Gemini Vision e retorna a análise estruturada.

        Tenta até _MAX_RETRIES vezes quando a validação Pydantic falha para que o
        modelo possa se autocorrigir. Faz fallback automático para _FALLBACK_MODEL
        quando o modelo principal retorna erro retriável (429, 500, 503, 504).
        """
        image_bytes = base64.b64decode(base64_str)

        contents = [
            types.Part.from_text(text=_SYSTEM_PROMPT),
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ]

        for model in (self._model_name, _FALLBACK_MODEL):
            print(f"--- CHAMANDO GEMINI API ({model}) ---")  # noqa: T201
            try:
                return self._call_with_guardrail_retries(model, contents)
            except (genai_errors.ServerError, genai_errors.ClientError) as exc:
                if exc.code in _FALLBACK_ON_CODES and model != _FALLBACK_MODEL:
                    print(  # noqa: T201
                        f"--- {model} falhou (HTTP {exc.code}), "
                        f"usando modelo fallback {_FALLBACK_MODEL} ---"
                    )
                    continue
                raise

        raise RuntimeError("All models unavailable")  # inalcançável, mas necessário para satisfazer o verificador de tipos

    def _call_with_guardrail_retries(
        self, model: str, contents: list[types.Part]
    ) -> AIAnalysisOutput:
        """Chama o modelo e tenta novamente até _MAX_RETRIES vezes quando a validação Pydantic falha."""
        last_error: Exception | None = None
        retry_contents = list(contents)

        for attempt in range(1, _MAX_RETRIES + 2):  # +2 = 1 tentativa inicial + número de retentativas
            response = self._client.models.generate_content(
                model=model,
                contents=retry_contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AIAnalysisOutput,
                ),
            )
            try:
                return AIAnalysisOutput.model_validate_json(response.text)
            except ValidationError as exc:
                last_error = exc
                if attempt <= _MAX_RETRIES:
                    print(  # noqa: T201
                        f"--- GUARDRAIL FALHOU (tentativa {attempt}) — "
                        f"reenviando ao modelo ---"
                    )
                    retry_contents.append(
                        types.Part.from_text(
                            text=(
                                f"Your previous response failed validation: {exc}. "
                                "Please fix the issues and respond again in the "
                                "exact JSON format requested."
                            )
                        )
                    )

        raise last_error  # type: ignore[misc]
