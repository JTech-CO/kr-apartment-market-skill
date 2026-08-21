"""Small compatibility shim so pure unit tests can import the package without MCP installed."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:  # pragma: no cover - exercised only when the optional runtime is installed
    from mcp.server.fastmcp import FastMCP as FastMCP
except ImportError:  # pragma: no cover - the fallback is covered indirectly in this environment

    class FastMCP:  # type: ignore[no-redef]
        """Minimal registration stub used only for local static tests."""

        def __init__(self, name: str):
            self.name = name
            self._tools: dict[str, Callable[..., Any]] = {}
            self.settings = type("Settings", (), {})()

        def tool(self, name: str | None = None, **_: Any):
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self._tools[name or func.__name__] = func
                return func

            return decorator

        def run(self, *_: Any, **__: Any) -> None:
            raise RuntimeError("The 'mcp' package is required to run the MCP server")

        def streamable_http_app(self) -> Any:
            raise RuntimeError("The 'mcp' package is required to run the MCP server")
