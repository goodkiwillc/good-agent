import pytest
from good_agent import Agent, AgentComponent, AgentEvents
from good_agent.core.event_router import EventContext, on


class DebugComponent(AgentComponent):
    """Minimal component for debugging decorator behavior."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.setup_called = False
        self.install_called = False

    @on(AgentEvents.AGENT_INIT_AFTER)
    def on_agent_init_decorator(self, ctx: EventContext) -> None:
        """Decorator handler for agent init."""
        self.events.append("decorator:init")
        print(f"Decorator handler fired: {ctx.parameters}")

    def setup(self, agent):
        """Setup method."""
        super().setup(agent)
        self.setup_called = True
        print("Setup called")

        # Manual handler to test
        @agent.on(AgentEvents.AGENT_INIT_AFTER, priority=50)
        def manual_init_handler(ctx):
            self.events.append("manual:init")
            print(f"Manual handler fired: {ctx.parameters}")

    async def install(self, agent):
        """Install method."""
        await super().install(agent)
        self.install_called = True
        print("Install called")


@pytest.mark.asyncio
async def test_decorator_debug():
    """Debug what's happening with decorators."""
    component = DebugComponent()

    # Check if decorator metadata exists
    print(
        f"Has decorator config: {hasattr(component.on_agent_init_decorator, '_event_handler_config')}"
    )
    if hasattr(component.on_agent_init_decorator, "_event_handler_config"):
        config = component.on_agent_init_decorator._event_handler_config
        print(f"Decorator config: {config}")

    # Check EventRouter events before agent creation
    print(f"Component events before agent: {list(component._events.keys())}")

    # Create agent
    print("Creating agent...")
    agent = Agent("Debug test", extensions=[component])

    # Check after agent creation but before ready
    print(f"Component events after agent creation: {list(component._events.keys())}")
    print(f"Setup called: {component.setup_called}")
    print(f"Component events so far: {component.events}")

    # Wait for agent to be ready
    print("Waiting for agent ready...")
    await agent.ready()

    print(f"Install called: {component.install_called}")
    print(f"Final component events: {component.events}")

    # Manual trigger of the event to test if handlers work
    print("Manually triggering AGENT_INIT_AFTER...")
    await agent.events.apply(AgentEvents.AGENT_INIT_AFTER, agent=agent)

    print(f"Events after manual trigger: {component.events}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
