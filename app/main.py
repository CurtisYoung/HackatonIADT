from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()  # carrega o .env antes que qualquer módulo leia variáveis de ambiente

from app.api.routes import router  # noqa: E402

app = FastAPI(
    title="IADT — AI Processing Microservice",
    description=(
        "Receives an architecture diagram (base64 or URL), "
        "processes it via Gemini Vision and returns structured analysis in JSON."
    ),
    version="0.1.0",
)

app.include_router(router)
