"""Entry point para rodar o MCP Server standalone."""
import uvicorn

if __name__ == "__main__":
    from app.mcp_server import mcp

    mcp.run(transport="streamable-http", mount_path="/mcp")