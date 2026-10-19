"""MCP server for analytics and CRM tools, served over streamable HTTP.

HTTP (not stdio) because the server runs as its own container next to the backend.
"""

import os

from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = MCPServer(name="ops-pilot-tools")


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=os.environ.get("MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCP_PORT", "8001")),
    )
