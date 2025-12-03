from typing import Any

from good_agent.agent.config import AgentConfigManager
from good_agent.core.components import AgentComponent


class _MockAgentEvents:
    """Lightweight facade that mimics :class:`Agent.events` for tests."""

    def __init__(self, agent: MockAgent) -> None:
        self._agent = agent
        self._event_trace_enabled = False

    async def apply(self, event: str, **kwargs: Any):
        return await self._agent.apply(event, **kwargs)

    async def apply_async(self, event: str, **kwargs: Any):  # pragma: no cover - alias
        return await self.apply(event, **kwargs)

    def apply_sync(self, event: str, **kwargs: Any):
        return self._agent.apply_sync(event, **kwargs)

    async def apply_typed(
        self,
        event: str,
        params_type: type | None,
        return_type: type | None,
        **kwargs: Any,
    ):
        return await self._agent.apply_typed(event, params_type, return_type, **kwargs)

    def apply_typed_sync(
        self,
        event: str,
        params_type: type | None,
        return_type: type | None,
        **kwargs: Any,
    ):
        return self._agent.apply_sync(event, **kwargs)

    def typed(self, params_type: type | None = None, return_type: type | None = None):
        async def _typed(event: str, **kwargs: Any):
            return await self.apply_typed(event, params_type, return_type, **kwargs)

        return _typed

    def broadcast_to(self, component: AgentComponent):
        return self._agent.broadcast_to(component)

    def consume_from(self, _other: Any):  # pragma: no cover - no-op
        return None

    def set_event_trace(self, enabled: bool, *, verbosity: int = 1, use_rich: bool = True):
        self._event_trace_enabled = enabled

    @property
    def event_trace_enabled(self) -> bool:
        return self._event_trace_enabled

    @property
    def ctx(self):
        from good_agent.core.event_router import EventContext

        return EventContext(parameters={}, output=None)

    async def join(self, timeout: float = 5.0):  # pragma: no cover - no-op
        return None

    def join_sync(self, timeout: float = 5.0):  # pragma: no cover - no-op
        return None

    async def close(self):  # pragma: no cover - no-op
        return None

    def close_sync(self):  # pragma: no cover - no-op
        return None


class MockAgent(Any):
    """Mock agent for testing AgentComponent subclasses.

    This mock provides the minimum interface needed for components
    that expect to be installed on an agent.
    """

    def __init__(self, **config_kwargs):
        """Initialize mock agent with optional config parameters."""
        self.config = AgentConfigManager(**config_kwargs)
        self._components = []
        self._broadcasts = []
        self._events = _MockAgentEvents(self)

    def broadcast_to(self, component: AgentComponent):
        """Mock broadcast_to method."""
        self._broadcasts.append(component)

    @property
    def events(self) -> _MockAgentEvents:
        return self._events

    def install_component(self, component: AgentComponent):
        """Install a component on this mock agent."""
        # Set agent reference and call setup (mimicking what real Agent does)
        component._agent = self
        self.broadcast_to(component)
        component.setup(self)
        self._components.append(component)
        return component

    async def apply(self, event: str, **kwargs: Any):
        return await self.apply_typed(event, None, None, **kwargs)

    async def apply_typed(self, event, params_type, return_type, **kwargs):
        """Mock apply_typed method for EventRouter compatibility."""
        from good_agent.core.event_router import EventContext

        # Extract output if provided (matching real EventRouter behavior)
        output = kwargs.get("output")

        # Return EventContext with parameters and preserved output
        return EventContext(parameters=kwargs, output=output)

    def apply_sync(self, event: str, **kwargs: Any):
        from good_agent.core.event_router import EventContext

        output = kwargs.get("output")
        return EventContext(parameters=kwargs, output=output)


def create_mock_agent_with_component(
    component_class: type[AgentComponent],
    agent_config: dict[str, Any] | None = None,
    component_kwargs: dict[str, Any] | None = None,
) -> tuple[MockAgent, AgentComponent]:
    """Create a mock agent with a component installed.

    Args:
        component_class: The component class to instantiate
        agent_config: Configuration parameters for the agent
        component_kwargs: Keyword arguments for the component

    Returns:
        Tuple of (mock_agent, component_instance)
    """
    agent_config = agent_config or {}
    component_kwargs = component_kwargs or {}

    # Create mock agent
    agent = MockAgent(**agent_config)

    # Create and install component
    component = component_class(**component_kwargs)
    agent.install_component(component)

    return agent, component
