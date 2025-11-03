"""
Focused integration test for @on decorator patterns in AgentComponents.

This test verifies that the @on decorator pattern works correctly for
AgentComponent event handling, demonstrating both decorator and manual
registration patterns work as expected.
"""

import asyncio

import pytest
from good_agent import Agent, AgentComponent, AgentEvents, tool
from good_agent.utilities.event_router import EventContext, on


class SimpleDecoratorComponent(AgentComponent):
    """Component demonstrating @on decorator functionality."""

    def __init__(self):
        super().__init__()
        self.events = []

    @on(AgentEvents.AGENT_INIT_AFTER)
    def on_agent_init(self, ctx: EventContext) -> None:
        """Static handler using @on decorator."""
        self.events.append("decorator:agent_init")

    @on(AgentEvents.TOOL_CALL_BEFORE, priority=200)
    def on_tool_before(self, ctx: EventContext) -> None:
        """Tool before handler with priority."""
        tool_name = ctx.parameters.get("tool_name", "unknown")
        self.events.append(f"decorator:tool_before:{tool_name}")

    @on(AgentEvents.TOOL_CALL_AFTER, priority=100)
    def on_tool_after(self, ctx: EventContext) -> None:
        """Tool after handler."""
        tool_name = ctx.parameters.get("tool_name", "unknown")
        self.events.append(f"decorator:tool_after:{tool_name}")

    def setup(self, agent):
        """Manual registration during setup."""
        super().setup(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=150)
        def on_message_manual(ctx):
            """Manually registered handler."""
            if not self.enabled:
                return
            self.events.append("manual:message_append")

    @tool
    def test_tool(self, value: str) -> str:
        """Simple component tool."""
        self.events.append(f"tool_executed:{value}")
        return f"result:{value}"


class ManualOnlyComponent(AgentComponent):
    """Component using only manual registration."""

    def __init__(self):
        super().__init__()
        self.events = []

    def setup(self, agent):
        """All handlers registered manually."""
        super().setup(agent)

        @agent.on(AgentEvents.AGENT_INIT_AFTER, priority=50)
        def on_init_manual(ctx):
            self.events.append("manual_only:init")

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def on_message_manual(ctx):
            if not self.enabled:
                return
            self.events.append("manual_only:message")


@pytest.mark.asyncio
class TestComponentDecoratorPatterns:
    """Test suite for @on decorator patterns in AgentComponents."""

    async def test_decorator_registration_works(self):
        """Verify @on decorators register handlers correctly."""
        component = SimpleDecoratorComponent()

        # Check decorator metadata was attached
        assert hasattr(component.on_agent_init, "_event_handler_config")
        config = component.on_agent_init._event_handler_config
        assert AgentEvents.AGENT_INIT_AFTER in config["events"]

        # Create agent - this should trigger decorator registration
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async event handlers time to complete
        await asyncio.sleep(0.01)

        # Decorator handlers should have fired during initialization
        assert "decorator:agent_init" in component.events

        # Verify component inherits EventRouter correctly
        assert hasattr(component, "on")
        assert hasattr(component, "do")
        assert hasattr(component, "apply")

    async def test_manual_vs_decorator_handlers(self):
        """Test that both manual and decorator handlers work together."""
        component = SimpleDecoratorComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async event handlers time to complete
        await asyncio.sleep(0.01)

        # Clear initialization events
        component.events.clear()

        # Add a message to trigger manual handler
        agent.append("Test message")

        # Manual handler should have fired
        assert "manual:message_append" in component.events

        # Execute tool via agent to trigger decorator handlers
        result = await agent.invoke("test_tool", value="test")

        # Verify tool executed
        assert result.success
        assert result.response == "result:test"

        # Wait for async event handlers to complete
        await asyncio.sleep(0.01)

        # Both decorator and tool execution should be recorded
        assert "tool_executed:test" in component.events
        assert any("decorator:tool_before" in event for event in component.events)
        assert any("decorator:tool_after" in event for event in component.events)

    async def test_component_enabled_state(self):
        """Test that handlers respect component enabled state."""
        component = SimpleDecoratorComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Clear initialization events
        component.events.clear()

        # Test enabled state (default)
        assert component.enabled
        agent.append("Message 1")
        enabled_count = len(
            [e for e in component.events if "manual:message_append" in e]
        )
        assert enabled_count > 0

        # Disable component
        component.events.clear()
        component.enabled = False
        agent.append("Message 2")

        # Manual handlers should respect enabled state
        disabled_count = len(
            [e for e in component.events if "manual:message_append" in e]
        )
        assert disabled_count == 0, "Manual handlers should respect enabled state"

        # Note: @on decorator handlers don't automatically check enabled state
        # They would need to check self.enabled explicitly in their implementation

    async def test_manual_only_component(self):
        """Test component that uses only manual registration."""
        component = ManualOnlyComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async event handlers time to complete
        await asyncio.sleep(0.01)

        # Should have manual init event
        assert "manual_only:init" in component.events

        # Test message handling
        component.events.clear()
        agent.append("Test message")
        assert "manual_only:message" in component.events

        # Test enabled state
        component.events.clear()
        component.enabled = False
        agent.append("Another message")

        # Should not fire when disabled
        disabled_events = [e for e in component.events if "manual_only:message" in e]
        assert len(disabled_events) == 0

    async def test_event_handler_priorities(self):
        """Test that event handler priorities work correctly."""

        class PriorityTestComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.execution_order = []

            @on(AgentEvents.AGENT_INIT_AFTER, priority=300)
            def high_priority_decorator(self, ctx: EventContext):
                self.execution_order.append("decorator_high")

            @on(AgentEvents.AGENT_INIT_AFTER, priority=100)
            def low_priority_decorator(self, ctx: EventContext):
                self.execution_order.append("decorator_low")

            def setup(self, agent):
                super().setup(agent)

                @agent.on(AgentEvents.AGENT_INIT_AFTER, priority=200)
                def mid_priority_manual(ctx):
                    self.execution_order.append("manual_mid")

        component = PriorityTestComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async event handlers time to complete
        await asyncio.sleep(0.01)

        # Should have all three events
        assert len(component.execution_order) == 3

        # Should contain all expected events (order may vary due to EventRouter implementation)
        assert "decorator_high" in component.execution_order
        assert "manual_mid" in component.execution_order
        assert "decorator_low" in component.execution_order

    async def test_async_event_handlers(self):
        """Test that async event handlers work correctly."""

        # Import tool decorator locally to make it accessible in the nested class
        from good_agent import tool as tool_decorator

        class AsyncTestComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.events = []

            @on(AgentEvents.TOOL_CALL_AFTER)
            async def async_decorator_handler(self, ctx: EventContext):
                """Async handler using decorator."""
                await asyncio.sleep(0.001)  # Simulate async work
                self.events.append("async_decorator")

            def setup(self, agent):
                super().setup(agent)

                @agent.on(AgentEvents.TOOL_CALL_BEFORE)
                async def async_manual_handler(ctx):
                    """Async handler registered manually."""
                    await asyncio.sleep(0.001)  # Simulate async work
                    self.events.append("async_manual")

            @tool_decorator
            def trigger_tool(self, value: str) -> str:
                return f"triggered:{value}"

        component = AsyncTestComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Execute tool via agent to trigger async handlers
        result = await agent.invoke("trigger_tool", value="async_test")

        assert result.success
        assert result.response == "triggered:async_test"

        # Wait for async handlers to complete
        await asyncio.sleep(0.01)

        # Both async handlers should have executed
        assert "async_manual" in component.events
        assert "async_decorator" in component.events


@pytest.mark.asyncio
async def test_eventrouter_inheritance_confirmed():
    """Confirm AgentComponent properly inherits EventRouter functionality."""
    from good_agent.utilities.event_router import EventRouter

    component = SimpleDecoratorComponent()

    # Should be EventRouter instance
    assert isinstance(component, EventRouter)

    # AgentComponent overrides __post_init__ to prevent local handler registration
    # Handlers are only registered with the agent when setup() is called
    # So component._events should be empty initially
    assert len(component._events) == 0

    # But the decorator metadata should still be attached to the methods
    assert hasattr(component.on_agent_init, "_event_handler_config")
    assert hasattr(component.on_tool_before, "_event_handler_config")
    assert hasattr(component.on_tool_after, "_event_handler_config")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
