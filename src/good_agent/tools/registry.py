import asyncio
import importlib.metadata
import logging
import os
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from re import Pattern
from typing import (
    TYPE_CHECKING,
    Any,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from good_agent.tools.tools import Tool


@dataclass
class ToolRegistration:
    """Registration information for a tool"""

    name: str
    tool: Tool
    tags: set[str] = field(default_factory=set)
    version: str = "1.0.0"
    description: str | None = None
    source: str = "manual"  # "manual", "entry_point", "auto_discovery"
    priority: int = 0  # Higher numbers = higher priority

    def matches_pattern(self, pattern: str) -> bool:
        """
        Check if this tool matches a selection pattern.

        Supported patterns:
        - "tool_name" - exact match
        - "tag:*" - all tools with tag
        - "tag:tool_name" - specific tool with tag
        - "*" - all tools
        """
        if pattern == "*":
            return True

        if pattern == self.name:
            return True

        if ":" in pattern:
            tag_part, name_part = pattern.split(":", 1)

            # Check if tool has the required tag
            if tag_part not in self.tags:
                return False

            # If name part is *, match any tool with the tag
            if name_part == "*":
                return True

            # Otherwise, check exact name match
            return name_part == self.name

        return False


class ToolRegistry:
    """
    Global registry for tool discovery and management.

    Supports:
    - Manual tool registration
    - Entry point discovery
    - Tag-based selection
    - Version management
    - Thread-safe operations
    """

    def __init__(self):
        self._tools: dict[str, ToolRegistration] = {}
        self._tags: dict[str, set[str]] = defaultdict(set)  # tag -> tool names
        self._compiled_patterns: dict[str, Pattern] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

        # Pending registrations queue for deferred registration
        self._pending_registrations: list[dict[str, Any]] = []
        self._pending_lock = threading.Lock()  # Thread-safe for sync access

    async def initialize(self, load_entry_points: bool = True) -> None:
        """
        Initialize the registry.

        Args:
            load_entry_points: Whether to load tools from entry points
        """
        async with self._lock:
            if self._initialized:
                return

            if load_entry_points:
                await self._load_entry_points()

            # Process any pending registrations
            await self._process_pending_registrations()

            self._initialized = True

    async def register(
        self,
        name: str,
        tool: Tool,
        *,
        tags: list[str] | None = None,
        version: str = "1.0.0",
        description: str | None = None,
        priority: int = 0,
        replace: bool = False,
    ) -> None:
        """
        Register a tool in the global registry.

        Args:
            name: Tool name (must be unique)
            tool: Tool instance
            tags: Optional list of tags for categorization
            version: Tool version (semver format)
            description: Optional description override
            priority: Priority for conflict resolution (higher wins)
            replace: Whether to replace existing tool with same name
        """
        async with self._lock:
            # Check for conflicts
            if name in self._tools and not replace:
                existing = self._tools[name]
                if existing.priority > priority:
                    # Existing tool has higher priority, skip registration
                    return
                elif existing.priority == priority:
                    logger.debug(
                        f"Tool '{name}' already registered with same priority. "
                        "Use replace=True to override."
                    )
                    return
                    # raise ValueError(
                    #     f"Tool '{name}' already registered. Use replace=True to override "
                    #     f"or set a higher priority."
                    # )

            # Create registration
            registration = ToolRegistration(
                name=name,
                tool=tool,
                tags=set(tags or []),
                version=version,
                description=description or getattr(tool, "description", None),
                source="manual",
                priority=priority,
            )

            # Remove old registration if exists
            if name in self._tools:
                await self._unregister_internal(name)

            # Register new tool
            self._tools[name] = registration

            # Update tag mappings
            for tag in registration.tags:
                self._tags[tag].add(name)

    async def unregister(self, name: str) -> bool:
        """
        Unregister a tool from the registry.

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was found and removed, False otherwise
        """
        async with self._lock:
            return await self._unregister_internal(name)

    async def _unregister_internal(self, name: str) -> bool:
        """Internal unregister method (assumes lock is held)"""
        if name not in self._tools:
            return False

        registration = self._tools[name]

        # Remove from tag mappings
        for tag in registration.tags:
            self._tags[tag].discard(name)
            if not self._tags[tag]:  # Remove empty tag
                del self._tags[tag]

        # Remove from tools
        del self._tools[name]
        return True

    async def get(self, name: str) -> Tool | None:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        async with self._lock:
            registration = self._tools.get(name)
            return registration.tool if registration else None

    async def get_registration(self, name: str) -> ToolRegistration | None:
        """
        Get tool registration information.

        Args:
            name: Tool name

        Returns:
            ToolRegistration or None if not found
        """
        async with self._lock:
            return self._tools.get(name)

    async def list_tools(self, pattern: str | None = None) -> list[ToolRegistration]:
        """
        List tools matching a pattern.

        Args:
            pattern: Selection pattern (e.g., "weather:*", "tool_name", "*")
                    If None, returns all tools

        Returns:
            List of matching tool registrations
        """
        async with self._lock:
            if pattern is None:
                return list(self._tools.values())

            return [
                registration
                for registration in self._tools.values()
                if registration.matches_pattern(pattern)
            ]

    async def select_tools(self, patterns: list[str]) -> dict[str, Tool]:
        """
        Select tools matching any of the given patterns.

        Args:
            patterns: List of selection patterns

        Returns:
            Dictionary mapping tool name to tool instance
        """
        selected = {}

        for pattern in patterns:
            matching = await self.list_tools(pattern)
            for registration in matching:
                selected[registration.name] = registration.tool

        return selected

    async def list_tags(self) -> dict[str, int]:
        """
        List all available tags with tool counts.

        Returns:
            Dictionary mapping tag name to number of tools
        """
        async with self._lock:
            return {tag: len(tool_names) for tag, tool_names in self._tags.items()}

    async def get_tools_by_tag(self, tag: str) -> list[ToolRegistration]:
        """
        Get all tools with a specific tag.

        Args:
            tag: Tag name

        Returns:
            List of tool registrations with the tag
        """
        async with self._lock:
            tool_names = self._tags.get(tag, set())
            return [self._tools[name] for name in tool_names if name in self._tools]

    async def clear(self) -> None:
        """
        Clear all registered tools from the registry.

        This is primarily useful for testing to ensure clean state between tests.
        """
        async with self._lock:
            self._tools.clear()
            self._tags.clear()
            self._compiled_patterns.clear()
            self._initialized = False

    async def _process_pending_registrations(self) -> None:
        """
        Process any registrations that were queued while in sync context.
        """
        with self._pending_lock:
            pending = self._pending_registrations.copy()
            self._pending_registrations.clear()

        for reg in pending:
            try:
                await self.register(**reg)
                logger.debug(f"Processed deferred registration for tool '{reg['name']}'")
            except Exception as e:
                logger.error(
                    f"Failed to process deferred registration for '{reg.get('name', 'unknown')}': {e}"
                )

    async def _load_entry_points(self) -> None:
        """Load tools from entry points"""
        # Skip entry point loading if disabled
        if os.environ.get("GOODINTEL_DISABLE_ENTRY_POINTS"):
            logger.debug("Entry point loading disabled via environment variable")
            return

        try:
            # Load from good_agent.tools entry point group
            entry_points = importlib.metadata.entry_points().select(group="good_agent.tools")

            for entry_point in entry_points:
                try:
                    # Load the tool function/class
                    tool_factory = entry_point.load()

                    # Extract metadata from entry point name
                    # Format: "tag1,tag2:tool_name" or just "tool_name"
                    ep_name = entry_point.name
                    if ":" in ep_name:
                        tag_part, name_part = ep_name.split(":", 1)
                        tags = [tag.strip() for tag in tag_part.split(",")]
                        tool_name = name_part
                    else:
                        tags = []
                        tool_name = ep_name

                    # Create tool instance
                    if callable(tool_factory):
                        # If it's a factory function, call it
                        tool = tool_factory()
                    else:
                        # If it's already a tool instance
                        tool = tool_factory

                    # Register with entry point source
                    registration = ToolRegistration(
                        name=tool_name,
                        tool=tool,
                        tags=set(tags),
                        version=getattr(tool, "version", "1.0.0"),
                        description=getattr(tool, "description", None),
                        source="entry_point",
                        priority=1,  # Entry points have medium priority
                    )

                    self._tools[tool_name] = registration

                    # Update tag mappings
                    for tag in registration.tags:
                        self._tags[tag].add(tool_name)

                except Exception:
                    # Log error but don't fail the entire initialization
                    # In production, would use proper logging
                    pass

        except Exception:
            # Entry point loading failed, continue without them
            pass

    def register_sync(
        self,
        name: str,
        tool: Tool,
        *,
        tags: list[str] | None = None,
        version: str = "1.0.0",
        description: str | None = None,
        priority: int = 0,
        replace: bool = False,
    ) -> None:
        """
        Synchronous version of register that works in all contexts.

        If called when an event loop is running (e.g., in Jupyter), queues
        the registration for later processing. Otherwise, registers immediately.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Queue for later registration when registry is accessed
                with self._pending_lock:
                    self._pending_registrations.append(
                        {
                            "name": name,
                            "tool": tool,
                            "tags": tags,
                            "version": version,
                            "description": description,
                            "priority": priority,
                            "replace": replace,
                        }
                    )
                logger.debug(f"Queued tool '{name}' for deferred registration")
                return
        except RuntimeError:
            # No event loop, create one
            pass

        # No running loop, can register immediately
        asyncio.run(
            self.register(
                name,
                tool,
                tags=tags,
                version=version,
                description=description,
                priority=priority,
                replace=replace,
            )
        )


# Global registry instance
_global_registry: ToolRegistry | None = None


async def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns:
        The global tool registry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
        await _global_registry.initialize()
    else:
        # Process any pending registrations that were queued
        await _global_registry._process_pending_registrations()

    return _global_registry


def get_tool_registry_sync() -> ToolRegistry:
    """
    Get the global tool registry instance (synchronous).

    Note: This creates a new event loop if none exists.

    Returns:
        The global tool registry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - can't initialize here
                # Return uninitialized registry and let caller handle it
                return _global_registry
        except RuntimeError:
            pass

        asyncio.run(_global_registry.initialize())

    return _global_registry


async def clear_tool_registry() -> None:
    """
    Clear the global tool registry.

    This is primarily useful for testing to ensure clean state between tests.
    """
    global _global_registry
    if _global_registry is not None:
        await _global_registry.clear()
        _global_registry = None


# Decorator for automatic tool registration
def register_tool(
    name: str | None = None,
    *,
    tags: list[str] | None = None,
    version: str = "1.0.0",
    description: str | None = None,
    priority: int = 0,
    auto_register: bool = True,
):
    """
    Decorator to automatically register a tool function.

    Args:
        name: Tool name (defaults to function name)
        tags: List of tags for categorization
        version: Tool version
        description: Tool description (defaults to docstring)
        priority: Registration priority
        auto_register: Whether to register immediately (vs. lazy registration)

    Example:
        @register_tool(tags=["weather"], version="1.1.0")
        def get_weather(location: str) -> str:
            '''Get weather for a location'''
            return f"Weather for {location}"
    """

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or ""
        tool_tags = tags or []

        if auto_register:
            # Register immediately
            # Create tool from function
            from good_agent.tools.tools import Tool

            tool = Tool(func)

            # Register synchronously (will create event loop if needed)
            registry = get_tool_registry_sync()
            registry.register_sync(
                tool_name,
                tool,
                tags=tool_tags,
                version=version,
                description=tool_description,
                priority=priority,
            )
        else:
            # Add metadata for lazy registration
            func._tool_registry_metadata = {  # type: ignore[attr-defined]
                "name": tool_name,
                "tags": tool_tags,
                "version": version,
                "description": tool_description,
                "priority": priority,
            }

        return func

    return decorator
