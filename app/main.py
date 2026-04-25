from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="IADT — AI Processing Microservice",
    description=(
        "Receives an architecture diagram (base64 or URL), "
        "processes it via Gemini Vision and returns structured analysis in JSON."
    ),
    version="0.1.0",
)

app.include_router(router)
