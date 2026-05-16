"""MCP Server standalone para análise de diagramas arquiteturais."""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from app.core.logging import get_logger

# Carrega .env automaticamente
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")

log = get_logger(__name__)

API_BASE_URL = os.getenv("IADT_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable must be set for MCP server")

mcp = FastMCP("diagram-analyzer")

UPLOAD_DIR = Path(os.getenv("MCP_UPLOAD_DIR", "/app/data/uploads"))


def _sniff_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if data.startswith(b"%PDF"):
        return ".pdf"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def _persist_base64(image_base64: str) -> str:
    """Persist a base64-encoded file to the upload directory and return its path."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(image_base64, validate=False)
    ext = _sniff_extension(data)
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    log.info(f"MCP persisted upload to {path} ({len(data)} bytes)")
    return str(path)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Endpoint de saúde para o K8s."""
    return JSONResponse({"status": "ok"})


async def _read_file_as_base64(file_path: str) -> str:
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {file_path}. "
                "Note que este servidor MCP está rodando remotamente e não tem acesso direto aos seus arquivos locais. "
                "Por favor, envie o conteúdo via 'image_base64'."
            )
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"Erro ao processar arquivo: {exc}")


def _serialize(output: Any) -> str:
    return json.dumps(output, indent=2, ensure_ascii=False)


async def _call_api(endpoint: str, file_path: str | None, image_base64: str | None, image_url: str | None = None) -> str:
    try:
        payload = {
            "model_type": "gemini"
        }

        if image_url:
            payload["image_url"] = image_url
        elif image_base64:
            payload["file_path"] = _persist_base64(image_base64)
        elif file_path:
            local = Path(file_path)
            if not local.exists():
                return (
                    f"Erro: arquivo '{file_path}' não existe no servidor MCP. "
                    "Envie via 'image_base64' (será persistido no volume compartilhado) "
                    "ou aponte para um path dentro de /app/data."
                )
            payload["file_path"] = str(local)
        else:
            return "Erro: Forneça 'image_url', 'image_base64' ou 'file_path'."

        log.info(f"MCP calling API: {endpoint}, model=gemini")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{API_BASE_URL}{endpoint}",
                json=payload,
                headers={"X-API-Key": API_KEY}
            )
            response.raise_for_status()
            return _serialize(response.json())
    except Exception as exc:
        log.error(f"MCP API error on {endpoint}: {exc}", exc_info=True)
        return f"Erro na operação: {exc}"


@mcp.tool()
async def analyze_diagram(file_path: str = None, image_base64: str = None, image_url: str = None) -> str:
    """Analisa um diagrama arquitetural (imagem ou PDF).

    Args:
        file_path: Caminho de arquivo já existente no volume compartilhado /app/data (ex: /app/data/uploads/foo.png). Não aceita paths do host do cliente.
        image_base64: Conteúdo do arquivo em base64. Será persistido em /app/data/uploads e processado pela API.
        image_url: URL pública da imagem. MELHOR alternativa para arquivos muito grandes se o servidor for remoto.
    """
    return await _call_api("/analyze/diagram/sync", file_path, image_base64, image_url)


@mcp.tool()
async def analyze_security(file_path: str = None, image_base64: str = None, image_url: str = None) -> str:
    """Realiza análise de segurança de um diagrama arquitetural.

    Args:
        file_path: Caminho de arquivo já existente no volume compartilhado /app/data (ex: /app/data/uploads/foo.png). Não aceita paths do host do cliente.
        image_base64: Conteúdo do arquivo em base64. Será persistido em /app/data/uploads e processado pela API.
        image_url: URL pública da imagem. MELHOR alternativa para arquivos muito grandes se o servidor for remoto.
    """
    return await _call_api("/analyze/security/sync", file_path, image_base64, image_url)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("MCP_PORT", 8001))
    mcp.settings.port = port
    mcp.run(transport="streamable-http")