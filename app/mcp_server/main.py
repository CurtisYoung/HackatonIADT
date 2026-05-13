"""Entry point para rodar o MCP Server standalone."""

if __name__ == "__main__":
    import os
    from app.mcp_server import mcp

    port = int(os.environ.get("MCP_PORT", 8001))
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    # Disable security restrictions for deployment behind Ingress
    mcp.settings.transport_security.enable_dns_rebinding_protection = False
    mcp.settings.transport_security.allowed_hosts = ["*"]
    mcp.run(transport="streamable-http")