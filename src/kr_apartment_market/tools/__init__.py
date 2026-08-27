"""MCP tool registration."""

from .canonical import register_canonical_tools
from .home import register_home_tools

__all__ = ["register_canonical_tools", "register_home_tools"]
