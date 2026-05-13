"""MCP Server standalone para análise de diagramas arquiteturais."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Carrega .env automaticamente
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")

API_BASE_URL = os.getenv("IADT_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "default-secret-key")

mcp = FastMCP("diagram-analyzer")


@mcp.custom_route("/mcp/health", methods=["GET"])
async def health_check(request):
    """Endpoint de saúde para o K8s."""
    return JSONResponse({"status": "ok"})


async def _read_file_as_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _serialize(output: Any) -> str:
    return json.dumps(output, indent=2, ensure_ascii=False)


async def _call_api(endpoint: str, file_path: str | None, image_base64: str | None) -> str:
    b64 = image_base64
    if file_path and not b64:
        b64 = await _read_file_as_base64(file_path)

    if not b64:
        return "Erro: É necessário fornecer 'file_path' ou 'image_base64'."

    payload = {
        "image_base64": b64,
        "model_type": "gemini"
    }
    if file_path:
        payload["file_path"] = file_path

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{API_BASE_URL}{endpoint}",
                json=payload,
                headers={"X-API-Key": API_KEY}
            )
            response.raise_for_status()
            return _serialize(response.json())
    except Exception as exc:
        return f"Erro ao chamar API: {exc}"


@mcp.tool()
async def analyze_diagram(file_path: str = None, image_base64: str = None) -> str:
    """Analisa um diagrama arquitetural (imagem ou PDF).

    Args:
        file_path: Caminho local do arquivo (imagem ou PDF).
        image_base64: Conteúdo da imagem em base64.
    """
    return await _call_api("/analyze/diagram/sync", file_path, image_base64)


@mcp.tool()
async def analyze_security(file_path: str = None, image_base64: str = None) -> str:
    """Realiza análise de segurança de um diagrama arquitetural.

    Args:
        file_path: Caminho local do arquivo (imagem ou PDF).
        image_base64: Conteúdo da imagem em base64.
    """
    return await _call_api("/analyze/security/sync", file_path, image_base64)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("MCP_PORT", 8001))
    mcp.settings.port = port
    mcp.run(transport="streamable-http")un(transport="streamable-http")