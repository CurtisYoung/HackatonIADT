from __future__ import annotations

import uuid
from typing import Callable

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.core.redis import get_redis_client

load_dotenv()  # carrega o .env antes que qualquer módulo leia variáveis de ambiente

from app.api.routes import router  # noqa: E402

log = get_logger(__name__)

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware que gera um ``X-Request-ID`` único para cada requisição e o inclui nos logs."""

    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        # Usa logger padrão e inclui request_id no log via extra
        log = get_logger(__name__)
        log.info(f"Incoming {request.method} {request.url.path}", extra={"request_id": request_id})
        
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            # Log do erro e propaga
            log.error(f"Error processing request {request_id}: {e}", extra={"request_id": request_id})
            raise

app = FastAPI(
    title="IADT - FIAP Secure Systems",
    description=(
        "API especializada na análise arquitetural de diagramas na nuvem, "
        "utilizando Gemini Vision com mitigação de alucinações (Guardrails) "
        "e fallback automático."
    ),
    version="1.0.0",
    contact={"name": "Equipe de Arquitetura"},
)

# CORS para desenvolvimento (permite todas origens)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de correlação de request ID
app.add_middleware(CorrelationIdMiddleware)

@app.get("/health", summary="Endpoint de saúde", response_model=dict, tags=["Public"])
async def health_check() -> dict:
    """Retorna o status de saúde da aplicação, verificando conexões críticas."""
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"
    return {"status": "ok", "redis": redis_status}

# Endpoint rápido para desenvolvedores
@app.get("/dev/info", tags=["Developer"], summary="Informações de desenvolvimento")
async def dev_info():
    """Retorna informações úteis ao desenvolvedor sem expor segredos."""
    from app.core.version import __version__  # Supondo que exista
    return {"app_version": __version__, "environment": "development"}

app.include_router(router)
