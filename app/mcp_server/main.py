"""Entry point para rodar o MCP Server standalone."""

if __name__ == "__main__":
    import os
    from app.mcp_server import mcp

    port = int(os.environ.get("MCP_PORT", 8001))
    mcp.settings.port = port
    mcp.run(transport="streamable-http")