from __future__ import annotations

import asyncio
import copy
import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from functools import update_wrapper
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Generic,
    Literal,
    ParamSpec,
    Protocol,
    TypeAlias,
    TypedDict,
    TypeVar,
    cast,
    get_args,
    get_type_hints,
    overload,
    runtime_checkable,
)

try:
    from typing import _AnnotatedAlias  # type: ignore
except ImportError:
    _AnnotatedAlias = None

import orjson
from fast_depends import Depends, dependency_provider, inject
from pydantic import (
    BaseModel,
    Field,
    create_model,
)
from pydantic._internal._core_utils import CoreSchemaOrField, is_core_schema
from pydantic.json_schema import GenerateJsonSchema
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from good_agent.core.components import AgentComponent
from good_agent.core.models import Renderable

logger = logging.getLogger(__name__)

ToolCallId: TypeAlias = str
ToolLike: TypeAlias = "Tool[..., Any] | Callable[..., Any] | Agent"

if TYPE_CHECKING:
    from good_agent.agent import Agent
    from good_agent.agent.config import AgentConfigManager
    from good_agent.extensions.template_manager.injection import (
        _ContextValueDescriptor,
    )
    from good_agent.mcp.client import MCPServerConfig
    from good_agent.tools.bound_tools import BoundTool
else:  # pragma: no cover - fallback for runtime to avoid circular imports
    Agent = Any  # type: ignore[assignment]
    MCPServerConfig = Any  # type: ignore[assignment]


@dataclass
class ToolContext:
    """Context passed to tools via dependency injection"""

    agent: Any  # Avoid circular import
    tool_call: ToolCall | None = None


# Provider functions for dependency injection
def _get_agent_provider():
    """Provider function to get Agent from dependency context.

    Value is provided via dependency_provider.override at call time.
    """
    return None


def _get_tool_call_provider():
    """Provider function to get ToolCall from dependency context.

    Value is provided via dependency_provider.override at call time.
    """
    return None


def _get_tool_context_provider(
    agent: Any = Depends(_get_agent_provider),
    tool_call: Any = Depends(_get_tool_call_provider),
):
    """Provider function to get ToolContext from dependency context"""
    return ToolContext(agent=agent, tool_call=tool_call)


def _get_message_provider():
    """Provider function to get last Message from Agent"""
    agent = _get_agent_provider()
    if agent and hasattr(agent, "messages") and agent.messages:
        return agent.messages[-1]
    return None


class ToolManager(AgentComponent):
    """Registers, discovers, and executes tools for an agent.

    Provides a single surface for local registrations, registry/MCP discovery, and
    dependency-injected execution with temporary override support. See
    ``examples/tools/basic_tool.py`` for a runnable walkthrough of registration,
    lookup, and execution patterns.
    """

    def __init__(self):
        """Initialize ToolManager with empty tool collection and MCP client.

        SIDE EFFECTS:
        - Creates empty internal tool dictionary
        - Initializes MCP client reference to None (lazy loading)
        - Sets up registry initialization flag
        - Calls parent AgentComponent initialization
        """
        self._tools: dict[str, Tool] = {}
        self._registry_initialized = False
        self._mcp_client = None  # Lazy-loaded MCP client manager
        super().__init__()

    def _export_state(self) -> dict[str, Any]:
        state = super()._export_state()
        state["tools"] = {name: copy.deepcopy(tool) for name, tool in self._tools.items()}
        return state

    def _import_state(self, state: dict[str, Any]) -> None:
        super()._import_state(state)
        tools = state.get("tools", {})
        self._tools = dict(tools.items())

    @property
    def config(self) -> AgentConfigManager:
        return self.agent.config

    async def _ensure_registry_initialized(self):
        """Ensure the global tool registry is initialized"""
        if not self._registry_initialized:
            from good_agent.tools.registry import get_tool_registry

            self._registry = await get_tool_registry()
            self._registry_initialized = True

    def __getitem__(self, tool_name: str) -> Tool:
        """Get a tool by name"""
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' not found")
        return self._tools[tool_name]

    def __setitem__(self, tool_name: str, tool: ToolLike) -> None:
        """Set a tool by name (accepts Tool or Callable)"""
        self._tools[tool_name] = self._ensure_tool(tool, tool_name)

    def __delitem__(self, tool_name: str) -> None:
        """Delete a tool by name"""
        if tool_name in self._tools:
            del self._tools[tool_name]
        else:
            raise KeyError(f"Tool '{tool_name}' not found")

    def __contains__(self, tool_name: str) -> bool:
        """Check if tool exists"""
        return tool_name in self._tools

    def keys(self):
        """Get all tool names"""
        return self._tools.keys()

    def values(self):
        """Get all tools"""
        return self._tools.values()

    def as_list(self) -> list[Tool]:
        """Get all tools as a list"""
        return list(self._tools.values())

    def items(self):
        """Get all tool name-tool pairs"""
        return self._tools.items()

    def __iter__(self):
        """Iterate over tool names"""
        return iter(self.values())

    def __len__(self) -> int:
        """Get number of tools"""
        return len(self._tools)

    async def load_tools_from_patterns(self, patterns: list[str]) -> None:
        """
        Load tools from the global registry based on selection patterns.

        Args:
            patterns: List of selection patterns (e.g., ["weather:*", "api_tool"])
        """
        await self._ensure_registry_initialized()

        # Select tools from registry
        selected_tools = await self._registry.select_tools(patterns)

        # Add to local tool collection
        self._tools.update(selected_tools)

    async def register_tool(
        self,
        tool: ToolLike,
        *,
        name: str | None = None,
        tags: list[str] | None = None,
        register_globally: bool = True,
        replace: bool = False,
    ) -> None:
        """
        Register a tool in this manager and optionally in the global registry.

        Args:
            name: Tool name
            tool: Tool instance or callable function
            tags: Optional tags for global registry
            register_globally: Whether to also register in global registry
        """

        name = name or (
            tool.name
            if isinstance(tool, Tool)
            else getattr(tool, "__name__", f"tool_{len(self._tools) + 1}")
        )

        assert name, "Tool must have a name"

        # Ensure it's a Tool instance
        tool_instance = self._ensure_tool(tool, name)

        # Add to local collection
        self._tools[name] = tool_instance

        # Register globally if requested
        if register_globally:
            await self._ensure_registry_initialized()
            await self._registry.register(name, tool_instance, tags=tags or [], replace=replace)

    def register_tool_sync(
        self,
        name: str,
        tool: ToolLike,
        *,
        tags: list[str] | None = None,
        register_globally: bool = True,
        replace: bool = False,
    ) -> None:
        """
        Synchronous version of register_tool for convenience.

        Note: Creates event loop if needed. Prefer async version when possible.
        """
        try:
            # Check if loop exists
            loop = asyncio.get_event_loop()
            # Check if loop is actually running (has thread associated)
            if loop.is_running():
                # If running, we can't use asyncio.run()
                # Instead we must schedule it on the current loop
                # But this is a sync method, so we can't return awaitable
                # This is tricky. For testing/CLI we usually want blocking.
                # If called from async context, user should use register_tool instead.

                # However, for __init__ where we need sync execution inside async loop:
                # We create a task and don't wait for it (fire and forget)
                # This is risky but needed for Agent() constructor inside async test
                loop.create_task(
                    self.register_tool(
                        tool,
                        name=name,
                        tags=tags,
                        register_globally=register_globally,
                        replace=replace,
                    )
                )
                return
        except RuntimeError:
            # No event loop exists, proceed to create one via asyncio.run
            pass

        asyncio.run(
            self.register_tool(
                tool,
                name=name,
                tags=tags,
                register_globally=register_globally,
                replace=replace,
            )
        )

    async def get_available_tools(self, pattern: str | None = None) -> dict[str, Tool]:
        """
        Get available tools from both local collection and global registry.

        Args:
            pattern: Optional pattern to filter tools

        Returns:
            Dictionary of tool name to tool instance
        """
        await self._ensure_registry_initialized()

        # Start with local tools
        available = dict(self._tools)

        # Add tools from global registry
        if pattern:
            registry_tools = await self._registry.select_tools([pattern])
        else:
            registry_registrations = await self._registry.list_tools()
            registry_tools = {reg.name: reg.tool for reg in registry_registrations}

        # Merge (local tools take precedence)
        for name, tool in registry_tools.items():
            if name not in available:
                available[name] = tool

        return available

    async def load_mcp_servers(
        self,
        server_configs: Sequence[str | dict[str, Any] | MCPServerConfig] | None,
    ) -> None:
        """
        Load tools from MCP servers.

        Args:
            server_configs: List of MCP server configurations
                Can be strings (URLs/commands) or dicts with full config
        """
        if not server_configs:
            return

        # Lazy-load MCP client manager
        if self._mcp_client is None:
            from good_agent.mcp import MCPClientManager

            self._mcp_client = MCPClientManager()
            # Set up MCP client with agent if available
            if self.agent:
                self._mcp_client._agent = self.agent
                self.agent.events.broadcast_to(self._mcp_client)
                self._mcp_client.setup(self.agent)

        # Connect to servers with normalized configs for typing compatibility
        normalized_configs: list[str | MCPServerConfig] = []
        for config in server_configs:
            if isinstance(config, str):
                normalized_configs.append(config)
            else:
                normalized_configs.append(cast(MCPServerConfig, config))

        await self._mcp_client.connect_servers(normalized_configs)

        # Get all tools from MCP servers
        mcp_tools = self._mcp_client.get_tools()

        # Add to our tool collection
        for tool_name, tool_adapter in mcp_tools.items():
            self._tools[tool_name] = tool_adapter
            logger.debug(f"Loaded MCP tool: {tool_name}")

        logger.info(f"Loaded {len(mcp_tools)} tools from {len(server_configs)} MCP servers")

    async def disconnect_mcp_servers(self) -> None:
        """Disconnect from all MCP servers and remove their tools."""
        if self._mcp_client:
            # Get MCP tool names before disconnecting
            mcp_tool_names = set(self._mcp_client.get_tools().keys())

            # Disconnect from servers
            await self._mcp_client.disconnect_all()

            # Remove MCP tools from our collection
            for tool_name in mcp_tool_names:
                if tool_name in self._tools:
                    del self._tools[tool_name]

            self._mcp_client = None

    def __call__(
        self,
        mode: Literal["replace", "append", "filter"] = "replace",
        tools: list[ToolLike] | None = None,
        filter_fn: Callable[[str, Tool], bool] | None = None,
    ):
        """
        Context manager for temporary tool modifications.

        Args:
            mode: How to modify tools
                - "replace": Replace all tools with provided ones
                - "append": Add new tools to existing ones
                - "filter": Filter existing tools with filter_fn
            tools: List of new tools to use (for replace/append modes)
            filter_fn: Function to filter tools (for filter mode)

        Returns:
            AsyncContextManager that yields the ToolManager

        Example:
            async with agent.tools(mode="replace", tools=[new_tool]):
                # Only new_tool is available here
                pass
            # Original tools restored
        """
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def tool_context():
            # Store original tools
            original_tools = dict(self._tools)

            try:
                # Apply the requested mode
                if mode == "replace":
                    self._tools.clear()
                    if tools:
                        for tool in tools:
                            # Get tool name from the tool object
                            if isinstance(tool, Tool):
                                name = tool.name
                            elif callable(tool):
                                name = getattr(tool, "__name__", str(tool))
                            else:
                                name = str(tool)
                            self._tools[name] = self._ensure_tool(tool, name)

                elif mode == "append":
                    if tools:
                        for tool in tools:
                            # Get tool name from the tool object
                            if isinstance(tool, Tool):
                                name = tool.name
                            elif callable(tool):
                                name = getattr(tool, "__name__", str(tool))
                            else:
                                name = str(tool)
                            self._tools[name] = self._ensure_tool(tool, name)

                elif mode == "filter":
                    if filter_fn:
                        filtered = {
                            name: tool
                            for name, tool in self._tools.items()
                            if filter_fn(name, tool)
                        }
                        self._tools.clear()
                        self._tools.update(filtered)

                # Yield the tool manager
                yield self

            finally:
                # Restore original tools
                self._tools.clear()
                self._tools.update(original_tools)

        return tool_context()

    def _ensure_tool(self, tool_or_callable: ToolLike, name: str | None = None) -> Tool[..., Any]:
        """
        Ensure we have a Tool instance, wrapping a callable if necessary.

        Args:
            tool_or_callable: Either a Tool instance or a callable to wrap
            name: Optional name for the tool (used if wrapping a callable)

        Returns:
            Tool instance
        """
        # Handle Agent instances by wrapping them
        # Import locally to avoid circular imports
        try:
            from good_agent.agent.core import Agent

            if isinstance(tool_or_callable, Agent):
                from good_agent.tools.agent_tool import AgentAsTool

                wrapped = AgentAsTool(tool_or_callable, name=name)
                return wrapped.as_tool()
        except ImportError:
            pass

        if isinstance(tool_or_callable, Tool):
            return tool_or_callable
        elif callable(tool_or_callable):
            # Wrap the callable in a Tool
            tool_name = name or tool_or_callable.__name__
            return Tool(
                fn=tool_or_callable,
                name=tool_name,
                description=inspect.getdoc(tool_or_callable) or f"Tool: {tool_name}",
            )
        else:
            raise TypeError(f"Expected Tool, Agent, or Callable, got {type(tool_or_callable)}")


class ToolCall(BaseModel):
    """Represents a tool call from the LLM"""

    id: ToolCallId
    type: str = "function"
    function: ToolCallFunction

    @property
    def name(self) -> str:
        """Convenience property to access function name"""
        return self.function.name

    @property
    def parameters(self) -> dict:
        """Convenience property to access function arguments as dict"""
        try:
            return orjson.loads(self.function.arguments)
        except Exception:
            return {}


T_Response = TypeVar("T_Response")


class ToolResponse(Renderable, Generic[T_Response]):
    """Response from a tool execution"""

    __template__ = "{{response}}"

    tool_name: str
    tool_call_id: ToolCallId | None = None
    response: T_Response
    parameters: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None


class ToolCallFunction(BaseModel):
    """Function details in a tool call"""

    name: str
    arguments: str  # JSON string of arguments


@dataclass
class ToolParameter:
    """Information about a tool parameter"""

    name: str
    type: Any
    description: str | None = None
    default: Any = inspect.Parameter.empty
    required: bool = True


@dataclass
class ToolMetadata:
    """Metadata about a tool function"""

    name: str
    description: str
    parameters: dict[str, ToolParameter] = field(default_factory=dict)
    register: bool = False  # Whether to register globally


# TypedDict definitions for tool signatures
class _ToolSignatureFunctionParameters(TypedDict):
    type: str
    properties: Any
    required: list[str]
    additionalProperties: bool


class _ToolSignatureFunction(TypedDict):
    name: str
    description: str
    parameters: _ToolSignatureFunctionParameters


class ToolSignature(TypedDict):
    type: Literal["function"]
    function: _ToolSignatureFunction


class BaseToolGenerateJsonSchema(GenerateJsonSchema):
    """Custom JSON schema generator for tools"""

    def field_title_should_be_set(self, schema: CoreSchemaOrField) -> bool:
        return_value = super().field_title_should_be_set(schema)
        if return_value and is_core_schema(schema):
            return False
        return return_value


@runtime_checkable
class BaseToolDefinition(Protocol):
    """Protocol for tool definitions"""

    name: str
    description: str
    fn: Callable

    @property
    def model(self) -> type[BaseModel]: ...

    @property
    def signature(self) -> ToolSignature: ...

    def __call__(self, *args, **kwargs) -> Any: ...


FuncResp = TypeVar("FuncResp")
P = ParamSpec("P")
# NOTE: Method tools can live on any instance type (components, resources, etc.)
# Do not constrain the instance type to AgentComponent for typing purposes.
InstanceSelf = TypeVar("InstanceSelf")


class Tool(BaseToolDefinition, Generic[P, FuncResp]):
    """Wrap a callable in schema generation, DI, and retry-aware execution.

    A Tool inspects type hints to build a Pydantic model, hides injectable
    parameters, and produces a `ToolResponse` when awaited. See
    ``examples/tools/basic_tool.py`` for both decorator and manual wrapping
    patterns.
    """

    _tool_metadata: ToolMetadata

    def __repr__(self) -> str:
        """Return concise tool representation for debugging.

        Returns:
            String with tool name, description, and parameter list
        """
        return f"<Tool name={self.name} description={self.description} params={list(self._tool_metadata.parameters.keys())}>"

    def __init__(
        self,
        fn: Callable[P, FuncResp],
        name: str | None = None,
        description: str | None = None,
        retry: bool = False,
        hide: list[str] | None = None,
        **config,
    ):
        # Store original function and check for string annotations
        self._original_fn = fn
        self._annotation_descriptions: dict[str, str] = {}
        self._hidden_params: set[str] = set(hide) if hide else set()

        # Auto-detect and hide injectable parameters to avoid JSON schema issues
        self._auto_hide_injectable_params(fn)

        has_string_annotations = self._check_for_string_annotations(fn)

        if has_string_annotations:
            # Skip modification for functions with string annotations
            modified_fn = fn
        else:
            # Modify function to add Depends() for injectable types
            modified_fn = self._modify_function_for_injection(fn)

        # Apply dependency injection
        self.fn = inject(modified_fn)

        if retry:
            self.fn = self._on_function_add_retry(self.fn)

        # Use original function for signature to preserve annotations
        self._signature = inspect.signature(self._original_fn)
        self.name = name or fn.__name__
        self.description = description or inspect.getdoc(fn) or ""
        self.config = config

        update_wrapper(self, fn)

        self._responses: list[ToolResponse[FuncResp]] = []

        # Extract parameters excluding hidden ones for metadata
        visible_params = extract_parameter_info(fn, exclude=self._hidden_params)

        # Also store all parameters (including hidden) for internal use
        self._all_params = extract_parameter_info(fn)

        self._tool_metadata = ToolMetadata(
            name=self.name,
            description=self.description,
            parameters=visible_params,
            register=config.get("register", False),
        )

    def _auto_hide_injectable_params(self, fn: Callable) -> None:
        """Automatically hide injectable parameters from JSON schema."""
        # Import lazily to avoid circular dependency
        from good_agent.extensions.template_manager.injection import (
            _ContextValueDescriptor,
        )

        # Check for ContextValue parameters first
        sig = inspect.signature(fn)
        for param_name, param in sig.parameters.items():
            if isinstance(param.default, _ContextValueDescriptor):
                self._hidden_params.add(param_name)

        # Then check for type-based injectable parameters
        try:
            hints = get_type_hints(fn, include_extras=True)
        except Exception:
            # If we can't get type hints, skip auto-hiding
            return

        for param_name, param_type in hints.items():
            if param_name in ("self", "cls"):
                continue

            type_name = getattr(param_type, "__name__", str(param_type))

            # Check if it's an injectable type
            if type_name in ("Agent", "ToolCall", "ToolContext", "Message"):
                self._hidden_params.add(param_name)
            elif hasattr(param_type, "__mro__"):
                # Check if it's an AgentComponent subclass
                try:
                    if issubclass(param_type, AgentComponent):
                        self._hidden_params.add(param_name)
                except (ImportError, TypeError):
                    pass

    def _check_for_string_annotations(self, fn: Callable) -> bool:
        """Check if function has Annotated types with string descriptions"""
        sig = inspect.signature(fn)

        for param_name, param in sig.parameters.items():
            if param.annotation == inspect.Parameter.empty:
                continue

            annotation = param.annotation

            # Check if it's an Annotated type in multiple ways
            is_annotated = False

            # Method 1: Check if it's an instance of _AnnotatedAlias
            try:
                if _AnnotatedAlias and isinstance(annotation, _AnnotatedAlias):
                    is_annotated = True
            except Exception:
                pass

            # Method 2: Check for __origin__ attribute
            if not is_annotated and hasattr(annotation, "__origin__"):
                origin = annotation.__origin__
                if (
                    hasattr(origin, "__name__")
                    and origin.__name__ == "Annotated"
                    or str(origin) == "typing.Annotated"
                ):
                    is_annotated = True

            # Method 3: Check string representation
            if not is_annotated and "Annotated[" in str(annotation):
                is_annotated = True

            if is_annotated and hasattr(annotation, "__metadata__"):
                for metadata in annotation.__metadata__:
                    if isinstance(metadata, str):
                        # Store the description for later use
                        self._annotation_descriptions[param_name] = metadata
                        return True

        return False

    def _modify_function_for_injection(self, fn: Callable) -> Callable:
        """
        Modify function to add Depends() for injectable types.
        This creates a new function with modified defaults.
        """
        sig = inspect.signature(fn)
        hints = get_type_hints(fn, include_extras=True)

        # Map of types to their provider functions
        type_providers = {}

        # Check each parameter for injectable types
        new_params = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                new_params.append(param)
                continue

            if param_name not in hints:
                new_params.append(param)
                continue

            param_type = hints[param_name]
            type_name = getattr(param_type, "__name__", str(param_type))

            # Check if it's an injectable type and doesn't already have Depends
            if param.default == inspect.Parameter.empty or not isinstance(
                param.default, type(Depends(lambda: None))
            ):
                provider = None

                if type_name == "Agent":
                    provider = _get_agent_provider
                elif type_name == "ToolCall":
                    provider = _get_tool_call_provider
                elif type_name == "ToolContext":
                    provider = _get_tool_context_provider
                elif type_name == "Message":
                    provider = _get_message_provider
                elif hasattr(param_type, "__mro__"):
                    # Check if it's an AgentComponent subclass
                    try:
                        if issubclass(param_type, AgentComponent):
                            # Create a provider for this extension type
                            def make_extension_provider(ext_type):
                                # Use fast_depends to inject the current Agent from the provider context
                                def extension_provider(
                                    agent: Any = Depends(_get_agent_provider),
                                ):
                                    if agent:
                                        try:
                                            return agent[ext_type]
                                        except (KeyError, TypeError):
                                            return None
                                    return None

                                return extension_provider

                            provider = make_extension_provider(param_type)
                    except (ImportError, TypeError):
                        pass

                if provider:
                    # Create new parameter with Depends default
                    new_param = param.replace(default=Depends(provider))
                    new_params.append(new_param)
                    type_providers[param_type] = provider
                else:
                    new_params.append(param)
            else:
                new_params.append(param)

        # If no modifications needed, return original
        if len(new_params) == len(sig.parameters) and all(
            p1 == p2 for p1, p2 in zip(new_params, sig.parameters.values(), strict=False)
        ):
            return fn

        # Create wrapper function with modified signature
        new_sig = sig.replace(parameters=new_params)

        # Create wrapper that applies the new signature
        if inspect.iscoroutinefunction(fn):

            async def wrapper(*args, **kwargs):  # type: ignore[reportRedeclaration]
                return await fn(*args, **kwargs)
        else:

            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)

        # Apply the new signature
        wrapper.__signature__ = new_sig  # type: ignore[attr-defined]
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__

        # Copy other attributes
        update_wrapper(wrapper, fn)

        return wrapper

    def _on_function_add_retry(self, fn: Callable[..., FuncResp]) -> Callable[..., FuncResp]:
        """Add retry logic to the function"""
        return retry(
            wait=wait_exponential(multiplier=1, min=4, max=10),
            stop=stop_after_attempt(3),
            # Use a standard logger instead of loguru for tenacity
            before_sleep=before_sleep_log(logging.getLogger(__name__), logging.INFO),
        )(fn)

    @property
    def signature(self) -> ToolSignature:
        """Get the tool signature in OpenAI format"""
        _schema = self.model.model_json_schema(schema_generator=BaseToolGenerateJsonSchema)
        return ToolSignature(
            type="function",
            function=_ToolSignatureFunction(
                name=self.name,
                description=self.description,
                parameters=_ToolSignatureFunctionParameters(
                    type=_schema.get("type", "object"),
                    properties=_schema.get("properties", {}),
                    required=_schema.get("required", []),
                    additionalProperties=_schema.get("additionalProperties", False),
                ),
            ),
        )

    def get_schema(self) -> dict[str, Any]:
        """Get the tool schema (wrapper for model_json_schema)"""
        return self.model.model_json_schema(schema_generator=BaseToolGenerateJsonSchema)

    @property
    def model(self) -> type[BaseModel]:
        """Generate Pydantic model from function signature (only visible parameters)"""
        # Create a dynamic model from the function signature excluding hidden params
        fields = {}
        # Use the visible parameters from metadata
        for param_name, param_info in self._tool_metadata.parameters.items():
            field_type = param_info.type

            if param_info.default != inspect.Parameter.empty:
                fields[param_name] = (field_type, param_info.default)
            else:
                fields[param_name] = (field_type, ...)

        # Convert fields dict to proper format for create_model
        field_definitions = {}
        for name, (field_type, default) in fields.items():
            if default is ...:
                field_definitions[name] = field_type
            else:
                field_definitions[name] = (field_type, default)

        # Create model with arbitrary_types_allowed to handle non-Pydantic types
        # This is needed for injected types like Agent, AgentComponent, etc.
        from pydantic import ConfigDict

        return create_model(
            f"{self.name}Model",
            __config__=ConfigDict(arbitrary_types_allowed=True),
            **field_definitions,
        )

    async def __call__(
        self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> ToolResponse[FuncResp]:
        """Execute the tool and return response"""
        # Import lazily to avoid circular dependency
        from good_agent.extensions.template_manager.injection import (
            ContextValue,
            _ContextValueDescriptor,
        )

        tool_call: ToolCall | None = None
        try:
            # Set up dependency injection context if available
            # Extract context from kwargs if provided
            agent = cast(Agent | None, kwargs.pop("_agent", None))
            tool_call = kwargs.pop("_tool_call", None)  # type: ignore[assignment]

            # Handle ContextValue injection
            sig = inspect.signature(self._original_fn)
            for param_name, param in sig.parameters.items():
                if isinstance(param.default, _ContextValueDescriptor) and param_name not in kwargs:
                    context_value: _ContextValueDescriptor = param.default
                    # Try to get from agent vars (template variables)
                    if agent and hasattr(agent, "vars"):
                        # Try to get the value from vars
                        context_val = agent.vars.get(context_value.name)
                        if context_val is not None:
                            kwargs[param_name] = context_val
                        elif context_value.default is not ContextValue._MISSING:  # type: ignore[attr-defined]
                            kwargs[param_name] = context_value.default
                        elif context_value.default_factory is not None:
                            kwargs[param_name] = context_value.default_factory()
                        elif not context_value.required:
                            kwargs[param_name] = None
                        else:
                            from good_agent.extensions.template_manager.injection import (
                                MissingContextValueError,
                            )

                            # Get available keys from vars if possible
                            available_keys = []
                            if hasattr(agent.vars, "as_dict"):
                                available_keys = list(agent.vars.as_dict().keys())
                            raise MissingContextValueError(context_value.name, available_keys)
                    else:
                        # No agent context available - use defaults if available
                        if context_value.default is not ContextValue._MISSING:  # type: ignore[attr-defined]
                            kwargs[param_name] = context_value.default
                        elif context_value.default_factory is not None:
                            kwargs[param_name] = context_value.default_factory()
                        elif not context_value.required:
                            kwargs[param_name] = None
                        else:
                            from good_agent.extensions.template_manager.injection import (
                                MissingContextValueError as MissingContextValueErrorRef,
                            )

                            raise MissingContextValueErrorRef(context_value.name, [])

            from contextlib import ExitStack

            with ExitStack() as stack:
                if agent is not None:
                    stack.enter_context(
                        dependency_provider.scope(_get_agent_provider, lambda: agent)
                    )
                if tool_call is not None:
                    stack.enter_context(
                        dependency_provider.scope(_get_tool_call_provider, lambda: tool_call)
                    )

                # Call the injected function; await if it returns an awaitable
                result = self.fn(*args, **kwargs)
                if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                    result = await result

            # Create response - handle if result is already a ToolResponse
            if isinstance(result, ToolResponse):
                # Tool returned a ToolResponse directly - use it but update fields
                response = ToolResponse(
                    tool_name=self.name,
                    response=result.response,  # Extract the actual response
                    parameters=result.parameters or kwargs,
                    success=result.success,
                    error=result.error,
                    tool_call_id=tool_call.id if tool_call else result.tool_call_id,
                )
            else:
                # Normal case - wrap the result
                response = ToolResponse(
                    tool_name=self.name,
                    response=result,
                    parameters=kwargs,
                    success=True,
                    tool_call_id=tool_call.id if tool_call else None,
                )

            # Store response
            self._responses.append(response)

            return response

        except Exception as e:
            # Create error response
            err_msg = str(e)
            # Normalize validation-related errors to include a standard phrase
            lower = err_msg.lower()
            if "validation error" not in lower and (
                "optionitem[" in lower or "incoming options" in lower or "field required" in lower
            ):
                err_msg = f"Validation error: {err_msg}"

            response = ToolResponse[FuncResp](
                tool_name=self.name,
                response=None,  # type: ignore[arg-type]
                parameters=kwargs,
                success=False,
                error=err_msg,
                tool_call_id=tool_call.id if tool_call else None,
            )

            # Store response
            self._responses.append(response)

            return response

    @property
    def results(self) -> list[ToolResponse[FuncResp]]:
        """Get all tool calls made"""
        return self._responses

    @property
    def calls(self) -> list[ToolCall]:
        """Get all tool calls made (stub - not implemented yet)"""
        # This would need to track actual ToolCall objects
        # For now return empty list
        return []


def wrap_callable_as_tool(
    func: Callable,
    name: str | None = None,
    description: str | None = None,
    retry: bool = False,
    hide: list[str] | None = None,
    **kwargs: Any,
) -> Tool:
    """
    Wrap a callable function as a Tool instance.

    This is a convenience function to convert regular functions into Tool objects
    without using the @tool decorator.

    Args:
        func: The callable to wrap
        name: Optional name for the tool (defaults to function name)
        description: Optional description (defaults to function docstring)
        retry: Whether to add retry logic
        hide: List of parameter names to hide from the tool definition
        **kwargs: Additional Tool configuration

    Returns:
        Tool instance wrapping the callable

    Example:
        def my_function(x: int, api_key: str) -> int:
            '''Multiply by two'''
            return x * 2

        tool_instance = wrap_callable_as_tool(my_function, hide=["api_key"])
        # Now tool_instance can be used wherever a Tool is expected
    """
    return Tool(
        fn=func,
        name=name or func.__name__,
        description=description or inspect.getdoc(func) or "",
        retry=retry,
        hide=hide,
        **kwargs,
    )


def extract_parameter_info(
    func: Callable, exclude: set[str] | None = None
) -> dict[str, ToolParameter]:
    """Extract parameter information from a function

    Args:
        func: The function to extract parameters from
        exclude: Set of parameter names to exclude from extraction
    """
    sig = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)
    parameters = {}
    exclude = exclude or set()

    for param_name, param in sig.parameters.items():
        # Skip special parameters like self, ctx (ToolContext)
        if param_name in ("self", "cls"):
            continue

        # Skip explicitly excluded parameters (hidden params)
        if param_name in exclude:
            continue

        param_type = type_hints.get(param_name, Any)

        # Check if it's ToolContext - skip it
        if param_type == ToolContext:
            continue

        # Extract description from Annotated
        description = None
        if hasattr(param_type, "__metadata__"):
            # Handle Annotated[type, description]
            for metadata in param_type.__metadata__:
                if isinstance(metadata, str):
                    description = metadata
                    break
            # Get the actual type from Annotated
            param_type = get_args(param_type)[0] if get_args(param_type) else param_type

        # Check for Pydantic Field
        if param.default != inspect.Parameter.empty:
            if hasattr(param.default, "description"):
                description = param.default.description

            # Extract default value from Field
            if hasattr(param.default, "default"):
                default_value = param.default.default
            else:
                default_value = param.default
        else:
            default_value = inspect.Parameter.empty

        required = param.default == inspect.Parameter.empty

        parameters[param_name] = ToolParameter(
            name=param_name,
            type=param_type,
            description=description,
            default=default_value,
            required=required,
        )

    return parameters


# Note: BoundTool import for type hints is handled at the top of the file if needed


# Method signature overload - for component methods (returns BoundTool descriptor)
# Note: This overload should be more restrictive, but TypeScript doesn't have a way
# to detect 'self' parameter statically. The runtime logic handles this correctly.
# Commenting out to fix type checker issues with standalone functions.
# @overload
# def tool(
#     func: Callable[..., FuncResp],  # Method with self parameter
# ) -> "BoundTool":  # Returns descriptor that preserves type info
#     ...


# TYPING NOTES (do not simplify these overloads without running mypy tests):
# - We intentionally use an unconstrained `InstanceSelf` TypeVar instead of binding
#   to AgentComponent. Resource classes (e.g., StatefulResource) also expose @tool
#   methods. Constraining to AgentComponent causes mypy to infer Never for
#   BoundTool.__get__ when the owner isn't AgentComponent, which then leads to
#   errors like duplicated `self` parameters or "Argument 1 has type 'str'; expected 'Never'".
# - The Callable[Concatenate[InstanceSelf, P], ...] form models an instance method
#   that includes `self`. BoundTool.__get__ returns a Tool[P, FuncResp] where `self`
#   has been bound and therefore removed from the callable signature.
# - FuncResp is left unconstrained to avoid odd inference cascades.
# - The matching overloads in bound_tools.py for BoundTool.__get__ are intentionally
#   wide (type[Any]/object) to prevent Never inference across components/resources.
#   If you alter one side, update both and re-run mypy on resource/component tests.
# - Symptoms of breaking these rules include mypy showing double `self` in method
#   signatures or Never-typed parameters in Tool calls.
#
# Overload for instance methods (sync/async)
@overload
def tool(
    func: Callable[Concatenate[InstanceSelf, P], Awaitable[FuncResp]],
) -> BoundTool[InstanceSelf, P, FuncResp] | Tool[P, FuncResp]: ...


@overload
def tool(
    func: Callable[Concatenate[InstanceSelf, P], FuncResp],
) -> BoundTool[InstanceSelf, P, FuncResp] | Tool[P, FuncResp]: ...


# Overload for async standalone functions
@overload
def tool(
    func: Callable[P, Awaitable[FuncResp]],
) -> BoundTool[Any, P, FuncResp] | Tool[P, FuncResp]: ...


# Overload for sync standalone functions
@overload
def tool(
    func: Callable[P, FuncResp],
) -> BoundTool[Any, P, FuncResp] | Tool[P, FuncResp]: ...


# Overload for decorator with arguments (returns decorator)
@overload
def tool(
    func: None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    register: bool = False,
    retry: bool = False,
    hide: list[str] | None = None,
    **kwargs: Any,
) -> Callable[
    [
        Callable[Concatenate[InstanceSelf, P], FuncResp]
        | Callable[Concatenate[InstanceSelf, P], Awaitable[FuncResp]]
        | Callable[P, FuncResp]
        | Callable[P, Awaitable[FuncResp]]
    ],
    Tool[P, FuncResp] | BoundTool[InstanceSelf, P, FuncResp],
]: ...


def tool(  # type: ignore[misc]
    func: Callable[P, FuncResp] | Callable[P, Awaitable[FuncResp]] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    register: bool = False,
    retry: bool = False,
    hide: list[str] | None = None,
    **kwargs: Any,
) -> (
    Tool[P, FuncResp]
    | BoundTool  # Still returned for methods at runtime
    | Callable[[Any], Tool[P, FuncResp] | BoundTool]
):
    """Decorator that turns a function or method into a Tool/BoundTool.

    Supports optional naming, retry, global registration, and hidden params. See
    ``examples/tools/basic_tool.py`` for decorator usage.
    """

    def decorator(
        f: Callable[P, FuncResp] | Callable[P, Awaitable[FuncResp]],
    ) -> Tool[P, FuncResp] | BoundTool:
        # Check if this is being applied to a method that will be part of an AgentComponent
        # We detect this by checking if 'self' is the first parameter
        import inspect

        sig = inspect.signature(f)
        params = list(sig.parameters.keys())

        # If the first parameter is 'self', this is likely a method
        if params and params[0] == "self":
            # For AgentComponent methods, create a BoundTool descriptor
            # that will return Tool instances bound to component instances
            from good_agent.tools.bound_tools import BoundTool

            # Extract metadata
            tool_name = name or f.__name__
            tool_description = description or inspect.getdoc(f) or ""

            # Create metadata object for the method
            metadata = ToolMetadata(
                name=tool_name,
                description=tool_description,
                parameters={},  # Will be filled by Tool class
                register=register,
            )

            # Create config dict
            config = {"retry": retry, "hide": hide or [], **kwargs}

            # Create and return BoundTool descriptor
            bound_tool: BoundTool[Any, P, FuncResp] = BoundTool(
                tool_class=Tool,
                unbound_method=f,  # type: ignore[arg-type]
                metadata=metadata,
                config=config,
            )

            # Preserve function attributes for introspection
            bound_tool.__name__ = f.__name__  # type: ignore[attr-defined]
            bound_tool.__doc__ = f.__doc__
            bound_tool.__module__ = f.__module__
            bound_tool.__qualname__ = f.__qualname__  # type: ignore[attr-defined]

            # Mark it as a bound tool for the metaclass
            bound_tool._is_bound_tool = True  # type: ignore[attr-defined]

            return bound_tool

        # For regular functions (not methods), create Tool instance as before
        tool_instance = Tool(
            fn=f,
            name=name,
            description=description,
            retry=retry,
            hide=hide,
            **kwargs,
        )

        # Extract metadata for compatibility
        tool_name = tool_instance.name
        tool_description = tool_instance.description

        # Extract parameters, excluding hidden ones for the metadata
        # Use the tool instance's metadata which already has hidden params filtered
        parameters = tool_instance._tool_metadata.parameters

        # Update parameter descriptions from Tool's annotation descriptions
        for param_name, param_info in parameters.items():
            if param_name in tool_instance._annotation_descriptions:
                param_info.description = tool_instance._annotation_descriptions[param_name]

        # Create metadata object for compatibility
        metadata = ToolMetadata(
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            register=register,
        )

        # Attach metadata to both function and tool instance
        # Use setattr to handle the union type properly
        f._tool_metadata = metadata  # type: ignore[union-attr]
        tool_instance._tool_metadata = metadata

        # If register=True, register the tool globally
        if register:
            # Import here to avoid circular dependency
            from good_agent.tools.registry import get_tool_registry_sync

            # Get the global registry
            registry = get_tool_registry_sync()

            # register_sync now handles both sync and async contexts gracefully
            # It will queue the registration if in async context (like Jupyter)
            registry.register_sync(
                tool_name,
                tool_instance,
                tags=kwargs.get("tags", []),  # Support tags parameter
                version=kwargs.get("version", "1.0.0"),  # Support version parameter
                description=tool_description,
                priority=kwargs.get("priority", 0),  # Support priority parameter,
                replace=True,
            )

        # Return the Tool instance
        return tool_instance  # type: ignore[return-value]

    # Handle both @tool and @tool()
    if func is None:
        return decorator
    else:
        return decorator(func)
