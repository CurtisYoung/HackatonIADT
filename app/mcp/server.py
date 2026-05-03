"""MCP Server para análise de diagramas arquiteturais.

Expõe as capacidades do sistema como ferramentas MCP (Model Context Protocol),
permitindo que qualquer cliente MCP (como Claude Code) analise diagramas de
arquitetura e realize análises de segurança.
"""

from __future__ import annotations

import base64
import json
import sys
from typing import Any

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    TextContent,
    Tool,
)

from app.domain.schemas import DiagramInput
from app.infrastructure.ai_client import AIClient
from app.infrastructure.file_repository import FileOutputRepository
from app.infrastructure.pdf_processor import process_pdf_and_encode_images
from app.usecases.analyze_diagram import AnalyzeDiagramUseCase
from app.usecases.security_analysis import SecurityAnalysisUseCase


def _serialize(output: Any) -> str:
    """Serializa um objeto Pydantic ou qualquer outro para JSON."""
    if hasattr(output, "model_dump"):
        return json.dumps(output.model_dump(), indent=2, ensure_ascii=False)
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
            componentes identificados, riscos arquiteturais e recomendações.

            Forneça o caminho do arquivo ou o conteúdo base64 da imagem.
            Para PDFs, o texto e a primeira imagem são extraídos automaticamente.""",
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
            (imagem ou PDF), identificando vulnerabilidades e recomendações de segurança.

            Forneça o caminho do arquivo ou o conteúdo base64 da imagem.""",
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


def _build_input(file_path: str | None, image_base64: str | None) -> DiagramInput:
    """Constrói DiagramInput a partir dos argumentos, tratando PDF se necessário."""
    b64: str | None = image_base64
    resolved_path: str | None = file_path

    if file_path and not image_base64:
        b64 = _read_file_as_base64(file_path)
        resolved_path = file_path

    if not b64:
        raise ValueError("É necessário fornecer 'file_path' ou 'image_base64'.")

    # model_type será definido pelo AIClient usando seu valor padrão
    return DiagramInput(image_base64=b64, file_path=resolved_path)  # type: ignore[arg-type]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "analyze_diagram":
            return await _handle_analyze_diagram(arguments)
        elif name == "analyze_security":
            return await _handle_analyze_security(arguments)
        else:
            raise ValueError(f"Ferramenta desconhecida: {name}")
    except Exception as exc:
        return [TextContent(type="text", text=f"Erro: {exc}")]


async def _handle_analyze_diagram(arguments: dict) -> list[TextContent]:
    file_path = arguments.get("file_path")
    image_base64 = arguments.get("image_base64")

    input_data = _build_input(file_path, image_base64)
    client = AIClient()  # Use default model from settings
    repo = FileOutputRepository()
    use_case = AnalyzeDiagramUseCase(ai_client=client, repository=repo)

    result = await use_case.execute(input_data)
    return [TextContent(type="text", text=_serialize(result))]


async def _handle_analyze_security(arguments: dict) -> list[TextContent]:
    file_path = arguments.get("file_path")
    image_base64 = arguments.get("image_base64")

    input_data = _build_input(file_path, image_base64)
    client = AIClient()  # Use default model from settings
    repo = FileOutputRepository()
    use_case = SecurityAnalysisUseCase(ai_client=client, repository=repo)

    result = await use_case.execute(input_data)
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
