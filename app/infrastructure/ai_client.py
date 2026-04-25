from __future__ import annotations

import base64
import os

import google.generativeai as genai
import instructor

from app.domain.schemas import AIAnalysisOutput

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


class GeminiClient:
    """Wraps the Gemini Vision call via google-generativeai + instructor."""

    def __init__(self, model_name: str = "gemini-1.5-flash") -> None:
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            raise ValueError(
                "The GOOGLE_API_KEY environment variable is not set."
            )
        genai.configure(api_key=api_key)
        self._client = instructor.from_gemini(
            client=genai.GenerativeModel(model_name=model_name),
            mode=instructor.Mode.GEMINI_JSON,
        )

    async def analyze_image(self, base64_str: str) -> AIAnalysisOutput:
        """Sends the image (base64) to Gemini Vision and returns the structured analysis."""
        image_bytes = base64.b64decode(base64_str)

        image_part = {
            "mime_type": "image/png",
            "data": image_bytes,
        }

        return self._client.chat.completions.create(
            response_model=AIAnalysisOutput,
            messages=[
                {"role": "user", "parts": [_SYSTEM_PROMPT, image_part]},
            ],
        )
