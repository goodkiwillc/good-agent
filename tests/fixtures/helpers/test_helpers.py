from typing import Any

from good_agent.components.component import AgentComponent
from good_agent.config import AgentConfigManager


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

    def broadcast_to(self, component: AgentComponent):
        """Mock broadcast_to method."""
        self._broadcasts.append(component)

    def install_component(self, component: AgentComponent):
        """Install a component on this mock agent."""
        # Set agent reference and call setup (mimicking what real Agent does)
        component._agent = self
        self.broadcast_to(component)
        component.setup(self)
        self._components.append(component)
        return component

    async def apply_typed(self, event, params_type, return_type, **kwargs):
        """Mock apply_typed method for EventRouter compatibility."""
        from good_agent.core.event_router import EventContext

        # Extract output if provided (matching real EventRouter behavior)
        output = kwargs.get("output", None)

        # Return EventContext with parameters and preserved output
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
