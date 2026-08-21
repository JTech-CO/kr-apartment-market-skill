"""Unified FastMCP server entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from kr_apartment_market.config import Settings
from kr_apartment_market.mcp_compat import FastMCP
from kr_apartment_market.tools import register_canonical_tools


def create_mcp(
    *,
    settings: Settings | None = None,
    enable_upstream_compat: bool | None = None,
) -> tuple[FastMCP, list[str]]:
    """Build one MCP instance containing canonical and optional compatibility tools."""
    load_dotenv(Path.cwd() / ".env")
    settings = settings or Settings.from_env()
    mcp = FastMCP("kr-apartment-market")
    names = register_canonical_tools(mcp, settings)
    use_compat = settings.enable_upstream_compat if enable_upstream_compat is None else enable_upstream_compat
    if use_compat:
        try:
            from real_estate.mcp_server.tools import register_all

            names.extend(register_all(mcp, settings))
        except Exception as exc:  # compatibility must not take down canonical tools
            print(f"warning: real-estate-mcp compatibility tools were not registered: {exc}")
    setattr(mcp, "kr_apartment_tool_names", tuple(names))
    return mcp, names


def _run_http(mcp: FastMCP, host: str, port: int) -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("uvicorn is required for streamable-http transport") from exc

    mcp.settings.host = host
    mcp.settings.port = port
    try:  # SDK versions differ; configure protection when the class is available.
        from mcp.server.transport_security import TransportSecuritySettings

        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=host in {"127.0.0.1", "localhost", "::1"}
        )
    except (ImportError, AttributeError, TypeError):
        pass
    app: Any = mcp.streamable_http_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="KR Apartment Market MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "http"],
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--no-upstream-compat",
        action="store_true",
        help="Expose only canonical kr_apartment.* tools",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Print registered tool names and exit",
    )
    args = parser.parse_args()

    mcp, names = create_mcp(enable_upstream_compat=not args.no_upstream_compat)
    if args.list_tools:
        print("\n".join(names))
        return
    if args.transport in {"streamable-http", "http"}:
        _run_http(mcp, args.host, args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
