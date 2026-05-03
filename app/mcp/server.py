"""MCP Server para análise de diagramas arquiteturais.

Este servidor atua como um cliente para a API do IADT, permitindo que ferramentas
MCP realizem análises sem necessidade de chaves de API locais.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    TextContent,
    Tool,
)

# Configuração da API
API_BASE_URL = os.getenv("IADT_API_URL", "http://localhost:8000")


def _serialize(output: Any) -> str:
    """Serializa um objeto para JSON."""
    return json.dumps(output, indent=2, ensure_ascii=False)


async def _read_file_as_base64(file_path: str) -> str:
    """Lê um arquivo do disco e retorna seu conteúdo codificado em base64."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


server = Server("diagram-analyzer")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_diagram",
            description="""Analisa um diagrama arquitetural (imagem ou PDF) e retorna
            componentes identificados, riscos arquiteturais e recomendações.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Caminho do arquivo no disco (imagem ou PDF)",
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Conteúdo da imagem codificado em base64",
                    },
                },
                "anyOf": [
                    {"required": ["file_path"]},
                    {"required": ["image_base64"]},
                ],
            },
        ),
        Tool(
            name="analyze_security",
            description="""Realiza uma análise de segurança de um diagrama arquitetural
            (imagem ou PDF), identificando vulnerabilidades e recomendações.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Caminho do arquivo no disco (imagem ou PDF)",
                    },
                    "image_base64": {
                        "type": "string",
                        "description": "Conteúdo da imagem codificado em base64",
                    },
                },
                "anyOf": [
                    {"required": ["file_path"]},
                    {"required": ["image_base64"]},
                ],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "analyze_diagram":
            return await _call_api("/analyze/diagram/sync", arguments)
        elif name == "analyze_security":
            return await _call_api("/analyze/security/sync", arguments)
        else:
            raise ValueError(f"Ferramenta desconhecida: {name}")
    except Exception as exc:
        return [TextContent(type="text", text=f"Erro ao chamar API: {exc}")]


async def _call_api(endpoint: str, arguments: dict) -> list[TextContent]:
    file_path = arguments.get("file_path")
    image_base64 = arguments.get("image_base64")

    if file_path and not image_base64:
        image_base64 = await _read_file_as_base64(file_path)

    payload = {
        "image_base64": image_base64,
        "file_path": file_path,
        "model_type": "gemini"  # Valor padrão para a API
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{API_BASE_URL}{endpoint}", json=payload)
        response.raise_for_status()
        result = response.json()

    return [TextContent(type="text", text=_serialize(result))]


async def main() -> None:
    """Entrypoint do MCP Server usando stdio transport."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="diagram-analyzer",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
