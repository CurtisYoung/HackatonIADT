"""Módulo MCP Server para análise de diagramas arquiteturais.

Expõe as funcionalidades do sistema via protocolo MCP,
permitindo integração com clientes como Claude Code.
"""

from app.mcp.server import mcp

__all__ = ["mcp"]
