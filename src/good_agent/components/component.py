from __future__ import annotations

import copy
import logging
from abc import ABCMeta
from typing import TYPE_CHECKING, Any, TypeVar

from good_agent.core.event_router import EventContext, EventRouter, on

from ..events import AgentEvents
from .tool_adapter import ToolAdapter, ToolAdapterRegistry

if TYPE_CHECKING:
    from ..agent import Agent
    from ..config import AgentConfigManager
    from ..events import ToolsGenerateSignature
    from ..tools import ToolSignature

logger = logging.getLogger(__name__)


class AgentComponentType(ABCMeta):
    """Metaclass for AgentComponent that collects tool methods."""

    _component_tools: dict[str, Any]

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Collect tool methods from this class and its bases
        cls._component_tools = {}

        # Walk through the MRO to collect all tool methods
        for base in reversed(cls.__mro__):
            for attr_name, attr_value in base.__dict__.items():
                # Check if this is a BoundTool descriptor
                if hasattr(attr_value, "_is_bound_tool"):
                    # This is a BoundTool descriptor created by the @tool decorator
                    cls._component_tools[attr_name] = attr_value
                # Also check for legacy tool-decorated methods (backward compatibility)
                elif hasattr(attr_value, "_tool_metadata"):
                    # This is a legacy tool-decorated method
                    cls._component_tools[attr_name] = attr_value
                elif (
                    hasattr(attr_value, "__class__")
                    and attr_value.__class__.__name__ == "Tool"
                ):
                    # This is a Tool instance (shouldn't happen but handle it)
                    cls._component_tools[attr_name] = attr_value

        return cls


T_AgentComponent = TypeVar("T_AgentComponent", bound="AgentComponent")


class AgentComponent(EventRouter, metaclass=AgentComponentType):
    """Base class for agent extensions with tool registration and lifecycle management.

    PURPOSE: Foundation for creating agent extensions that can add tools, handle events,
    and participate in the agent's dependency injection system.

    ROLE: Enables agent extension development through:
    - Tool method discovery and registration via @tool decorator
    - Event handling for agent lifecycle integration
    - Dependency injection for component composition
    - Configuration access and customization
    - Resource management and cleanup

    ARCHITECTURE:
    1. Tool Discovery: Metaclass automatically discovers @tool-decorated methods
    2. Dependency Resolution: Automatic dependency injection based on __depends__
    3. Event Integration: Inherits from EventRouter for agent event handling
    4. Lifecycle Management: Setup/install phases for initialization
    5. Resource Cleanup: Automatic cleanup when agent is destroyed

    DEPENDENCY INJECTION:
    Components can declare dependencies using class-level __depends__ attribute:
    ```python
    class MyComponent(AgentComponent):
        __depends__ = ["LanguageModel", "ToolManager"]

        def setup(self, agent):
            # Dependencies automatically available
            self.model = self.get_dependency("LanguageModel")
            self.tool_manager = self.get_dependency("ToolManager")
    ```

    TOOL REGISTRATION:
    Methods decorated with @tool automatically become available to the agent:
    ```python
    class SearchComponent(AgentComponent):
        @tool
        async def search_web(self, query: str) -> str:
            # This tool is automatically registered with the agent
            return await search_api(query)
    ```

    EVENT INTEGRATION:
    Components can listen to agent events using the @component.on decorator:
    ```python
    class LoggingComponent(AgentComponent):
        @component.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def log_message(self, ctx):
            print(f"Message: {ctx.parameters['message'].content}")
    ```

    LIFECYCLE MANAGEMENT:
    1. Class Creation: Metaclass discovers tools and validates dependencies
    2. Instantiation: Component created, dependencies resolved later
    3. Setup Phase: setup() called with agent reference for synchronous init
    4. Install Phase: install() called for async initialization and tool registration
    5. Runtime: Component actively handles events and provides tools
    6. Cleanup: Automatic cleanup when agent is destroyed

    THREAD SAFETY:
    - Component instances should not be shared between agents
    - Tool methods are thread-safe when called through agent
    - Event handlers should be careful with shared state
    - Dependency injection provides isolated instances

    PERFORMANCE CONSIDERATIONS:
    - Component initialization: ~1-5ms per component
    - Tool discovery: ~1ms per tool method
    - Event registration: ~1ms per event handler
    - Memory: ~1-5KB per component base + tool instances

    EXTENSION PATTERNS:
    - Tool Components: Components that primarily add tools to the agent
    - Event Components: Components that primarily handle agent events
    - Service Components: Components that provide services to other components
    - Monitoring Components: Components that track metrics and performance
    - Configuration Components: Components that manage agent configuration

    ERROR HANDLING:
    - Missing dependencies: ComponentDependencyError during agent initialization
    - Tool registration failures: Logged warnings, component continues to work
    - Event handler exceptions: Logged warnings, don't stop agent execution
    - Setup/install failures: Component marked as failed, agent may continue without it

    EXAMPLES:
    ```python
    # Simple tool component
    class WeatherComponent(AgentComponent):
        @tool
        async def get_weather(self, location: str) -> str:
            return await weather_api.get_current(location)


    # Component with dependencies
    class AnalysisComponent(AgentComponent):
        __depends__ = ["ToolManager", "LanguageModel"]

        def setup(self, agent):
            self.tool_manager = self.get_dependency("ToolManager")
            self.model = self.get_dependency("LanguageModel")

        async def install(self):
            await self.tool_manager.register_tool(
                Tool(self.analyze_text, name="analyze")
            )


    # Event handling component
    class LoggingComponent(AgentComponent):
        @component.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def log_message(self, ctx):
            logger.info(f"Message: {ctx.parameters['message'].role}")
    ```
    """

    _agent: Agent | None
    _component_tools: dict[str, Any]  # Populated by metaclass
    __depends__: list[
        str
    ] = []  # List of required component class names (for documentation/validation only)

    def __init__(self, *args, enabled: bool = True, **kwargs):
        """
        Initialize the component with optional enable/disable.

        Args:
            enabled: Whether this component is enabled (default: True)
            *args: Additional arguments passed to EventRouter
            **kwargs: Additional keyword arguments
        """
        super().__init__(*args, **kwargs)
        self._agent = None
        self._enabled = enabled
        self._registered_tool_names: list[str] = []
        self._tool_adapter_registry = ToolAdapterRegistry()
        # Don't call _auto_register_handlers() here - we'll register with agent in setup()

    def __post_init__(self):
        """Override EventRouter's __post_init__ to prevent double registration.

        We skip auto-registering handlers on the component itself since they
        will be registered with the agent during setup(). This prevents
        duplicate handler execution via both broadcast and direct registration.
        """
        # Skip self._auto_register_handlers() to prevent double registration
        # Handlers will be registered with the agent in setup() via
        # _register_decorated_handlers_with_agent()

    def _clone_init_args(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Return positional and keyword arguments for clone construction."""
        return (), {}

    def _export_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {"enabled": self._enabled}
        if self._tool_adapter_registry._adapters:
            state["tool_adapters"] = list(self._tool_adapter_registry._adapters)
        return state

    def _import_state(self, state: dict[str, Any]) -> None:
        self._enabled = state.get("enabled", True)
        for adapter in state.get("tool_adapters", []):
            adapter_clone = copy.deepcopy(adapter)
            adapter_clone.component = self
            self._tool_adapter_registry.register(adapter_clone)

    def clone(self: T_AgentComponent) -> T_AgentComponent:
        args, kwargs = self._clone_init_args()
        try:
            clone = type(self)(*args, **kwargs)
        except TypeError as exc:
            raise TypeError(
                f"{type(self).__name__} must implement _clone_init_args to support cloning"
            ) from exc
        clone._import_state(self._export_state())
        return clone

    def setup(self, agent: Agent):
        """
        Perform synchronous setup during component registration.

        This method is called synchronously when the component is registered,
        before the system message is set. Use this for registering event handlers
        that need to be active during Agent.__init__.

        For async initialization (loading resources, connecting to services),
        use the async install() method instead.

        Args:
            agent: The agent instance being set up
        """
        # Set the agent reference
        # Note: Use 'is not None' because Agent has __len__ which can make bool(agent) == False
        if agent is not None:
            self._agent = agent

        # Register decorated event handlers with the agent
        self._register_decorated_handlers_with_agent(agent)

        # Default implementation does nothing else
        # Override in subclasses that need early event handler registration

    async def install(self, agent: Agent):
        """
        Apply the component to the agent.

        This async method is called during agent initialization after all
        components have been registered and dependencies validated.

        Override this method to define how the component interacts with the agent.
        Common tasks include:
        - Setting up additional event handlers
        - Registering tools
        - Initializing resources
        - Connecting to external services

        Note: The agent reference is already set and events are already subscribed
        during registration, so you don't need to call broadcast_to() here.

        Args:
            agent: The agent instance to install on
        """
        # Note: Use 'is not None' because Agent has __len__ which can make bool(agent) == False
        if agent is not None:
            self._agent = agent

        # Agent reference and event subscription already done in _register_extension
        # Just register component tools if we have any
        if self._component_tools:
            self._register_component_tools()

        # Set up tool adapter event handlers if we have adapters
        # if self._tool_adapter_registry._adapters:
        #     self._setup_adapter_handlers()

    def _register_decorated_handlers_with_agent(self, agent: Agent) -> None:
        """Register decorated event handlers with the agent."""
        # Find all methods with event handler metadata
        for name in dir(self):
            if name.startswith("__"):
                continue
            try:
                # Get the unbound method from the class to check for decorator metadata
                class_attr = getattr(type(self), name, None)
                if class_attr and hasattr(class_attr, "_event_handler_config"):
                    # Get the bound method from the instance
                    bound_method = getattr(self, name)
                    config = class_attr._event_handler_config

                    # Register each event with the agent
                    for event in config["events"]:
                        agent.on(
                            event,
                            priority=config["priority"],
                            predicate=config.get("predicate"),
                        )(bound_method)
            except Exception:
                # Skip any attributes that can't be accessed
                pass

    def get_dependency(
        self, component_class: type[T_AgentComponent]
    ) -> T_AgentComponent | None:
        """
        Get a component dependency from the agent.

        Args:
            component_class: The component class type to look up

        Returns:
            The component instance or None if not found
        """
        if not self._agent:
            return None

        try:
            return self._agent[component_class]
        except KeyError:
            return None

    def _register_component_tools(self):
        """Register all tool methods from this component with the agent."""
        if self._agent is None:
            return

        from ..tools.bound_tools import BoundTool
        from ..tools.tools import wrap_callable_as_tool

        # Register each tool method
        for method_name, method in self._component_tools.items():
            # Check if this is a BoundTool descriptor
            if isinstance(method, BoundTool):
                # Get the Tool instance bound to this component instance
                tool_instance = getattr(self, method_name)
                tool_name = method.metadata.name

                # Register with the agent's tool manager
                try:
                    self._agent.tools[tool_name] = tool_instance
                    self._registered_tool_names.append(tool_name)
                except Exception as e:
                    logger.error(
                        f"Failed to register tool {tool_name}: {e}", exc_info=True
                    )

            # Handle legacy tool-decorated methods (backward compatibility)
            elif hasattr(method, "_tool_metadata"):
                # Get the actual bound method from this instance
                bound_method = getattr(self, method_name)
                metadata = method._tool_metadata
                config = getattr(method, "_tool_config", {})
                tool_name = metadata.name
                # logger.debug(f"Legacy method {method_name} has metadata with name {tool_name}")

                # The bound method already doesn't have 'self' in its signature
                # Just wrap it as a tool directly
                tool_instance = wrap_callable_as_tool(
                    bound_method,
                    name=tool_name,
                    description=metadata.description,
                    retry=config.get("retry", False),
                    hide=config.get("hide", []),
                    **{k: v for k, v in config.items() if k not in ["retry", "hide"]},
                )

                # Register with the agent's tool manager
                try:
                    self._agent.tools[tool_name] = tool_instance
                    self._registered_tool_names.append(tool_name)
                    # logger.debug(f"Registered tool {tool_name} with agent")
                except Exception as e:
                    logger.error(
                        f"Failed to register tool {tool_name}: {e}", exc_info=True
                    )

    def _unregister_component_tools(self):
        """Unregister all component tools from the agent."""
        if not self._agent:
            return

        # Remove registered tools
        for tool_name in self._registered_tool_names:
            if tool_name in self._agent.tools:
                del self._agent.tools[tool_name]

        self._registered_tool_names.clear()

    def register_tool_adapter(self, adapter: ToolAdapter):
        """
        Register a tool adapter with this component.

        Tool adapters allow components to intercept and modify tool behavior
        transparently. They can:
        - Modify tool signatures sent to the LLM
        - Transform parameters from LLM calls
        - Optionally transform tool responses

        Args:
            adapter: The tool adapter to register
        """
        self._tool_adapter_registry.register(adapter)

        # If already installed on an agent, set up handlers
        # if self._agent is not None and not hasattr(self, "_adapter_handlers_setup"):
        #     self._setup_adapter_handlers()

    def unregister_tool_adapter(self, adapter: ToolAdapter):
        """
        Unregister a tool adapter from this component.

        Args:
            adapter: The tool adapter to unregister
        """
        self._tool_adapter_registry.unregister(adapter)

    # def _setup_adapter_handlers(self):
    #     """Set up event handlers for tool adaptation."""
    #     if not self._agent or hasattr(self, "_adapter_handlers_setup"):
    #         return

    #     # Register handlers for tool adaptation events
    #     # Use high priority to ensure adapters run before other handlers
    #     # self._agent.on(AgentEvents.TOOLS_GENERATE_SIGNATURE, priority=200)(
    #     #     self._on_tools_generate_signature_adapter
    #     # )
    #     # self._agent.on(AgentEvents.TOOL_CALL_BEFORE, priority=200)(
    #     #     self._on_tool_call_before_adapter
    #     # )
    #     # self._agent.on(AgentEvents.TOOL_CALL_AFTER, priority=50)(
    #     #     self._on_tool_call_after_adapter
    #     # )

    #     self._adapter_handlers_setup = True

    @on(AgentEvents.TOOLS_GENERATE_SIGNATURE, priority=200)
    def _on_tools_generate_signature_adapter(
        self, ctx: EventContext[ToolsGenerateSignature, ToolSignature]
    ):
        """Handle tool signature adaptation for the LLM."""
        if not self.enabled or not self._tool_adapter_registry._adapters:
            return

        tool = ctx.parameters.get("tool")
        signature = ctx.output
        agent = ctx.parameters.get("agent")

        if not tool or not signature or not agent:
            return

        # Apply adapters to transform the signature
        adapted_signature = self._tool_adapter_registry.adapt_signature(
            tool, signature, agent
        )

        # Update the output if signature was modified
        if adapted_signature != signature:
            ctx.output = adapted_signature

    @on(AgentEvents.TOOL_CALL_BEFORE, priority=200)
    async def _on_tool_call_before_adapter(self, ctx: EventContext):
        """Handle parameter adaptation before tool execution."""
        if not self.enabled or not self._tool_adapter_registry._adapters:
            return

        tool_name = ctx.parameters.get("tool_name")
        parameters = ctx.parameters.get("parameters")

        if not tool_name or parameters is None:
            return

        # Apply adapters to transform parameters back to original format
        if self._agent is not None:
            adapted_params = self._tool_adapter_registry.adapt_parameters(
                tool_name, parameters, self._agent
            )
        else:
            adapted_params = parameters

        # Update the parameters if they were modified
        if adapted_params != parameters:
            ctx.parameters["parameters"] = adapted_params
            # Also update output for compatibility
            ctx.output = adapted_params

    @on(AgentEvents.TOOL_CALL_AFTER, priority=50)
    async def _on_tool_call_after_adapter(self, ctx: EventContext):
        """Handle response adaptation after tool execution."""
        if not self.enabled or not self._tool_adapter_registry._adapters:
            return

        tool_name = ctx.parameters.get("tool_name")
        response = ctx.parameters.get("response")

        if not tool_name or not response:
            return

        from ..tools import ToolResponse

        if not isinstance(response, ToolResponse):
            return

        # Apply adapters to transform the response
        if self._agent is not None:
            adapted_response = self._tool_adapter_registry.adapt_response(
                tool_name, response, self._agent
            )
        else:
            adapted_response = response

        # Update the response if it was modified
        if adapted_response != response:
            ctx.parameters["response"] = adapted_response

    @property
    def agent(self) -> Agent:
        """
        Returns the agent this component is installed on.
        """
        assert self._agent is not None, "This component is not installed on an agent"
        return self._agent

    @property
    def config(self) -> AgentConfigManager:
        return self.agent.config

    @property
    def enabled(self) -> bool:
        """Check if this component is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable this component."""
        if value != self._enabled:
            self._enabled = value
            if value:
                # Re-register tools when enabling
                self._register_component_tools()
            else:
                # Unregister tools when disabling
                self._unregister_component_tools()
