"""Standalone compatibility entry point for previous real-estate-mcp clients."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from kr_apartment_market.config import Settings
from kr_apartment_market.mcp_compat import FastMCP
from real_estate.mcp_server.tools import register_all


def create_mcp() -> FastMCP:
    load_dotenv(Path.cwd() / ".env")
    settings = Settings.from_env()
    mcp = FastMCP("real-estate")
    register_all(mcp, settings)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Vendored real-estate-mcp compatibility server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    mcp = create_mcp()
    if args.transport == "http":
        import uvicorn

        mcp.settings.host = args.host
        mcp.settings.port = args.port
        uvicorn.run(mcp.streamable_http_app(), host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
