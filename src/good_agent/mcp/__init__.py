from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .adapter import MCPToolAdapter
    from .client import MCPClientManager

__all__ = [
    "MCPClientManager",
    "MCPToolAdapter",
]


def __getattr__(name: str):
    """Lazy import for MCP components."""
    if name == "MCPClientManager":
        from .client import MCPClientManager

        return MCPClientManager
    elif name == "MCPToolAdapter":
        from .adapter import MCPToolAdapter

        return MCPToolAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
