"""MCP Server para análise de diagramas arquiteturais.

Implementado usando FastMCP para suportar múltiplos transportes, incluindo
Streamable HTTP para integração direta via URL.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Configuração da API
API_BASE_URL = os.getenv("IADT_API_URL", "http://localhost:8000")

# Criação do servidor FastMCP
mcp = FastMCP("diagram-analyzer")


async def _read_file_as_base64(file_path: str) -> str:
    """Lê um arquivo do disco e retorna seu conteúdo codificado em base64."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _serialize(output: Any) -> str:
    """Serializa um objeto para JSON."""
    return json.dumps(output, indent=2, ensure_ascii=False)


async def _call_api(endpoint: str, file_path: str | None, image_base64: str | None) -> str:
    """Encaminha a solicitação para a API principal."""
    b64 = image_base64
    if file_path and not b64:
        b64 = await _read_file_as_base64(file_path)

    if not b64:
        return "Erro: É necessário fornecer 'file_path' ou 'image_base64'."

    payload = {
        "image_base64": b64,
        "file_path": file_path,
        "model_type": "gemini"
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{API_BASE_URL}{endpoint}", json=payload)
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
    # Permite rodar como stdio transport se necessário
    mcp.run()
