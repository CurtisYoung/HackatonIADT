from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()  # carrega o .env antes que qualquer módulo leia variáveis de ambiente

from app.api.routes import router  # noqa: E402

app = FastAPI(
    title="IADT - FIAP Secure Systems",
    description=(
        "API especializada na análise arquitetural de diagramas na nuvem, "
        "utilizando Gemini Vision com mitigação de alucinações (Guardrails) "
        "e Fallback automático."
    ),
    version="1.0.0",
    contact={
        "name": "Equipe de Arquitetura",
    },
)

app.include_router(router)
