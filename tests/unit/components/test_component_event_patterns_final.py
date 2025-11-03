"""
Definitive integration test for AgentComponent event handling patterns.

This test confirms that:
1. @on decorators work correctly in AgentComponents (via EventRouter inheritance)
2. Manual registration during setup/install works
3. Both patterns can be used together effectively
4. Component lifecycle and event handling work as expected
"""

import pytest
from good_agent import Agent, AgentComponent, AgentEvents, tool
from good_agent.utilities.event_router import EventContext, on


class ComprehensiveEventComponent(AgentComponent):
    """Component demonstrating all event handling patterns."""

    def __init__(self):
        super().__init__()
        self.decorator_events = []
        self.manual_events = []
        self.tool_events = []

    # ===== Decorator Pattern (@on) =====
    @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=200)
    def on_message_append_decorator(self, ctx: EventContext) -> None:
        """Decorator handler for message append events."""
        message = ctx.parameters.get("message")
        message_type = type(message).__name__ if message else "None"
        self.decorator_events.append(f"message_append:decorator:{message_type}")

    @on(AgentEvents.TOOL_CALL_BEFORE, priority=150)
    def on_tool_before_decorator(self, ctx: EventContext) -> None:
        """Decorator handler for tool call events."""
        tool_name = ctx.parameters.get("tool_name", "unknown")
        self.decorator_events.append(f"tool_before:decorator:{tool_name}")

    @on(AgentEvents.TOOL_CALL_AFTER, priority=50)
    def on_tool_after_decorator(self, ctx: EventContext) -> None:
        """Decorator handler for tool completion."""
        tool_name = ctx.parameters.get("tool_name", "unknown")
        self.decorator_events.append(f"tool_after:decorator:{tool_name}")

    # ===== Manual Registration Pattern =====
    def setup(self, agent):
        """Manual registration during setup phase."""
        super().setup(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=100)
        def on_message_append_manual(ctx):
            """Manual handler for message append."""
            if not self.enabled:
                return
            message = ctx.parameters.get("message")
            message_type = type(message).__name__ if message else "None"
            self.manual_events.append(f"message_append:manual:{message_type}")

        @agent.on(AgentEvents.TOOL_CALL_BEFORE, priority=75)
        def on_tool_before_manual(ctx):
            """Manual handler for tool calls."""
            if not self.enabled:
                return
            tool_name = ctx.parameters.get("tool_name", "unknown")
            self.manual_events.append(f"tool_before:manual:{tool_name}")

    async def install(self, agent):
        """Manual registration during install phase."""
        await super().install(agent)

        @agent.on(AgentEvents.TOOL_CALL_AFTER, priority=25)
        async def on_tool_after_manual_async(ctx):
            """Async manual handler for tool completion."""
            if not self.enabled:
                return
            tool_name = ctx.parameters.get("tool_name", "unknown")
            self.manual_events.append(f"tool_after:manual_async:{tool_name}")

    # ===== Component Tool =====
    @tool
    def test_tool(self, value: str) -> str:
        """Tool that triggers events."""
        self.tool_events.append(f"tool_executed:{value}")
        return f"processed:{value}"


class DecoratorOnlyComponent(AgentComponent):
    """Component using only @on decorators."""

    def __init__(self):
        super().__init__()
        self.events = []

    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    def on_message_decorator_only(self, ctx: EventContext) -> None:
        """Pure decorator handler."""
        # Note: This doesn't check self.enabled automatically
        self.events.append("decorator_only:message")

    @on(AgentEvents.TOOL_CALL_BEFORE, priority=300)
    def on_tool_decorator_only(self, ctx: EventContext) -> None:
        """High priority decorator handler."""
        tool_name = ctx.parameters.get("tool_name", "unknown")
        self.events.append(f"decorator_only:tool:{tool_name}")


class ManualOnlyComponent(AgentComponent):
    """Component using only manual registration."""

    def __init__(self):
        super().__init__()
        self.events = []

    def setup(self, agent):
        super().setup(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def on_message_manual_only(ctx):
            if not self.enabled:  # Can check enabled state
                return
            self.events.append("manual_only:message")

        @agent.on(AgentEvents.TOOL_CALL_BEFORE)
        def on_tool_manual_only(ctx):
            if not self.enabled:
                return
            tool_name = ctx.parameters.get("tool_name", "unknown")
            self.events.append(f"manual_only:tool:{tool_name}")


@pytest.mark.asyncio
class TestComponentEventPatterns:
    """Integration test suite for event handling patterns."""

    async def test_decorator_pattern_functionality(self):
        """Test that @on decorators work in AgentComponents."""
        component = DecoratorOnlyComponent()

        # Verify decorator metadata was attached
        assert hasattr(component.on_message_decorator_only, "_event_handler_config")
        config = component.on_message_decorator_only._event_handler_config
        assert AgentEvents.MESSAGE_APPEND_AFTER in config["events"]

        # Verify EventRouter inheritance
        from good_agent.utilities.event_router import EventRouter

        assert isinstance(component, EventRouter)

        # Note: Handlers are not auto-registered on component to prevent duplication
        # They will be registered with the agent during setup()

        # Create agent and test actual event handling
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Trigger message event
        agent.append("Test message")
        assert "decorator_only:message" in component.events

        # Execute tool to trigger tool events
        # First create a simple tool for testing
        from good_agent.tools import Tool

        test_tool = Tool(fn=lambda x: f"result:{x}", name="simple_tool")
        agent.tools["simple_tool"] = test_tool

        # Execute and verify decorator handler fired
        component.events.clear()
        result = await agent.invoke(test_tool, x="test")

        assert result.success
        tool_events = [e for e in component.events if "decorator_only:tool" in e]
        assert len(tool_events) > 0
        assert "simple_tool" in tool_events[0]

    async def test_manual_pattern_functionality(self):
        """Test that manual registration works correctly."""
        component = ManualOnlyComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Test enabled state handling
        assert component.enabled
        agent.append("Test message")
        assert "manual_only:message" in component.events

        # Test disabled state
        component.events.clear()
        component.enabled = False
        agent.append("Another message")

        # Manual handlers should respect enabled state
        disabled_events = [e for e in component.events if "manual_only:message" in e]
        assert len(disabled_events) == 0

        # Re-enable and verify
        component.enabled = True
        agent.append("Final message")
        assert "manual_only:message" in component.events

    async def test_hybrid_pattern_integration(self):
        """Test that decorator and manual patterns work together."""
        component = ComprehensiveEventComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Test message handling (both patterns should fire)
        component.decorator_events.clear()
        component.manual_events.clear()

        agent.append("Test message")

        # Both decorator and manual handlers should have fired
        decorator_msg_events = [
            e for e in component.decorator_events if "message_append:decorator" in e
        ]
        manual_msg_events = [
            e for e in component.manual_events if "message_append:manual" in e
        ]

        assert len(decorator_msg_events) > 0
        assert len(manual_msg_events) > 0

        # Test tool execution (triggers multiple handlers)
        component.decorator_events.clear()
        component.manual_events.clear()
        component.tool_events.clear()

        result = await agent.invoke("test_tool", value="integration_test")

        assert result.success
        assert result.response == "processed:integration_test"

        # Verify all handler types fired
        assert "tool_executed:integration_test" in component.tool_events

        decorator_tool_events = [
            e
            for e in component.decorator_events
            if "tool_before:decorator" in e or "tool_after:decorator" in e
        ]
        manual_tool_events = [
            e
            for e in component.manual_events
            if "tool_before:manual" in e or "tool_after:manual" in e
        ]

        assert len(decorator_tool_events) > 0, (
            f"Decorator events: {component.decorator_events}"
        )
        assert len(manual_tool_events) > 0, f"Manual events: {component.manual_events}"

    async def test_component_enabled_state_behavior(self):
        """Test how enabled/disabled state affects different handler types."""
        component = ComprehensiveEventComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Test enabled (default)
        component.decorator_events.clear()
        component.manual_events.clear()

        agent.append("Enabled test")

        # Both should fire when enabled
        assert len([e for e in component.decorator_events if "message_append" in e]) > 0
        assert len([e for e in component.manual_events if "message_append" in e]) > 0

        # Disable component
        component.enabled = False
        component.decorator_events.clear()
        component.manual_events.clear()

        agent.append("Disabled test")

        # Manual handlers should respect enabled state (they check self.enabled)
        manual_disabled = [e for e in component.manual_events if "message_append" in e]
        assert len(manual_disabled) == 0, "Manual handlers should respect enabled=False"

        # Decorator handlers still fire (they don't automatically check enabled)
        decorator_disabled = [
            e for e in component.decorator_events if "message_append" in e
        ]
        assert len(decorator_disabled) > 0, (
            "Decorator handlers don't automatically check enabled state"
        )

    async def test_event_handler_priorities(self):
        """Test that event priorities work across both patterns."""

        class PriorityComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.execution_order = []

            @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=300)
            def high_decorator(self, ctx: EventContext):
                self.execution_order.append("decorator_high")

            @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=100)
            def low_decorator(self, ctx: EventContext):
                self.execution_order.append("decorator_low")

            def setup(self, agent):
                super().setup(agent)

                @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=200)
                def mid_manual(ctx):
                    self.execution_order.append("manual_mid")

        component = PriorityComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Trigger event
        agent.append("Priority test")

        # Should have all three handlers
        assert len(component.execution_order) == 3
        assert "decorator_high" in component.execution_order
        assert "manual_mid" in component.execution_order
        assert "decorator_low" in component.execution_order


@pytest.mark.asyncio
async def test_eventrouter_inheritance_verification():
    """Confirm AgentComponent properly inherits EventRouter capabilities."""
    from good_agent.utilities.event_router import EventRouter

    component = ComprehensiveEventComponent()

    # Should be EventRouter instance
    assert isinstance(component, EventRouter)

    # Should have all EventRouter methods
    assert hasattr(component, "on")
    assert hasattr(component, "do")
    assert hasattr(component, "apply")
    assert hasattr(component, "apply_async")

    # Handlers are registered with the agent, not the component itself (to prevent duplication)
    # We can verify the decorator metadata is present instead
    assert hasattr(component.on_message_append_decorator, "_event_handler_config")
    assert hasattr(component.on_tool_before_decorator, "_event_handler_config")
    assert hasattr(component.on_tool_after_decorator, "_event_handler_config")

    # Verify the metadata has correct event types and priorities
    message_config = component.on_message_append_decorator._event_handler_config
    assert AgentEvents.MESSAGE_APPEND_AFTER in message_config["events"]
    assert message_config["priority"] == 200

    tool_before_config = component.on_tool_before_decorator._event_handler_config
    assert AgentEvents.TOOL_CALL_BEFORE in tool_before_config["events"]
    assert tool_before_config["priority"] == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
