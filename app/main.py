from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="IADT — Microsserviço de Processamento de IA",
    description=(
        "Recebe um diagrama de arquitetura (base64 ou URL), "
        "processa via Gemini Vision e devolve análise estruturada em JSON."
    ),
    version="0.1.0",
)

app.include_router(router)
