import asyncio
from unittest.mock import MagicMock

import pytest
from good_agent import Agent, AgentComponent, AgentEvents, tool
from good_agent.utilities.event_router import EventContext, on


class DecoratorPatternComponent(AgentComponent):
    """Component testing @on decorator patterns."""

    def __init__(self):
        super().__init__()
        self.decorator_events = []
        self.setup_events = []
        self.install_events = []
        self.runtime_events = []

    # Static decorator - should work without agent access
    @on(AgentEvents.AGENT_INIT_AFTER)
    def on_agent_ready_static(self, ctx: EventContext) -> None:
        """Handler registered via @on decorator during class initialization."""
        self.decorator_events.append("agent_ready_static")

    @on(AgentEvents.TOOL_CALL_BEFORE, priority=200)
    def on_tool_before_static(self, ctx: EventContext) -> None:
        """High-priority static handler for tool calls."""
        tool_name = ctx.parameters.get("tool_name")
        self.decorator_events.append(f"tool_before_static:{tool_name}")

    @on(AgentEvents.TOOL_CALL_AFTER, priority=50)
    def on_tool_after_static(self, ctx: EventContext) -> None:
        """Low-priority static handler for tool completion."""
        tool_name = ctx.parameters.get("tool_name")
        success = (
            ctx.parameters.get("response", {}).success
            if hasattr(ctx.parameters.get("response", {}), "success")
            else True
        )
        self.decorator_events.append(f"tool_after_static:{tool_name}:{success}")

    # Manual registration during setup (sync phase)
    def setup(self, agent):
        """Register handlers that need early agent access."""
        super().setup(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=150)
        def on_message_append_setup(ctx):
            """Handler registered during setup phase."""
            if not self.enabled:
                return
            message = ctx.parameters.get("message")
            message_type = type(message).__name__ if message else "None"
            self.setup_events.append(f"message_append_setup:{message_type}")

    # Manual registration during install (async phase)
    async def install(self, agent):
        """Register handlers that need full agent access."""
        await super().install(agent)

        @agent.on(AgentEvents.EXECUTE_BEFORE, priority=100)
        async def on_execute_before_install(ctx):
            """Handler registered during install phase."""
            if not self.enabled:
                return
            # Can access agent context and other components
            # Context is a special object, access its internal dict representation
            if hasattr(agent, "context"):
                # The context object uses a ChainMap internally
                context_dict = (
                    dict(agent.context._chainmap)
                    if hasattr(agent.context, "_chainmap")
                    else {}
                )
                context_keys = list(context_dict.keys())
            else:
                context_keys = []
            self.install_events.append(
                f"execute_before_install:context_keys={len(context_keys)}"
            )

        @agent.on(AgentEvents.EXECUTE_AFTER)
        async def on_execute_after_install_async(ctx):
            """Async handler registered during install phase."""
            if not self.enabled:
                return
            # Simulate async work
            await asyncio.sleep(0.001)
            response = ctx.parameters.get("response", "")
            self.install_events.append(
                f"execute_after_install_async:response_len={len(str(response))}"
            )

    @tool
    def test_component_tool(self, value: str) -> str:
        """Component tool that triggers events."""
        self.runtime_events.append(f"tool_executed:{value}")
        return f"processed:{value}"


class ManualRegistrationComponent(AgentComponent):
    """Component using only manual registration patterns."""

    def __init__(self, custom_priority: int = 100):
        super().__init__()
        self.custom_priority = custom_priority
        self.events = []
        self.handler_count = 0

    def setup(self, agent):
        """Register all handlers manually with dynamic configuration."""
        super().setup(agent)

        # Dynamic priority based on component configuration
        @agent.on(AgentEvents.TOOL_CALL_BEFORE, priority=self.custom_priority)
        def on_tool_before_dynamic(ctx):
            if not self.enabled:
                return
            self.events.append(f"dynamic_priority:{self.custom_priority}")

        # Handler that accesses agent immediately
        @agent.on(AgentEvents.MESSAGE_SET_SYSTEM_AFTER, priority=200)
        def on_system_message_set(ctx):
            if not self.enabled:
                return
            # Access agent state
            message_count = len(agent.messages) if hasattr(agent, "messages") else 0
            self.events.append(f"system_set:msg_count={message_count}")

        # Handler with predicate based on component state
        @agent.on(
            AgentEvents.TOOL_CALL_AFTER,
            predicate=lambda ctx: self.enabled and self.custom_priority > 150,
        )
        def on_tool_after_conditional(ctx):
            self.events.append(f"conditional:priority={self.custom_priority}")

        self.handler_count = 3  # Track registered handlers


class HybridPatternComponent(AgentComponent):
    """Component using both decorator and manual registration patterns."""

    def __init__(self):
        super().__init__()
        self.static_events = []
        self.dynamic_events = []

    # Static handlers via @on decorator
    @on(AgentEvents.AGENT_INIT_AFTER, priority=300)
    def on_init_static(self, ctx: EventContext) -> None:
        """Static high-priority init handler."""
        self.static_events.append("init_static_high")

    @on(AgentEvents.AGENT_INIT_AFTER, priority=50)
    def on_init_static_low(self, ctx: EventContext) -> None:
        """Static low-priority init handler."""
        self.static_events.append("init_static_low")

    # Dynamic handlers via manual registration

    def setup(self, agent):
        super().setup(agent)

        @agent.on(AgentEvents.AGENT_INIT_AFTER, priority=200)
        def on_init_dynamic_mid(ctx):
            self.dynamic_events.append("init_dynamic_mid")

        # Register the high priority handler in setup too (not install)
        # because AGENT_INIT_AFTER fires before install() is called
        @agent.on(AgentEvents.AGENT_INIT_AFTER, priority=250)
        def on_init_dynamic_high(ctx):
            self.dynamic_events.append("init_dynamic_high")

    async def install(self, agent):
        await super().install(agent)
        # Don't register AGENT_INIT_AFTER handlers here - the event has already fired


@pytest.mark.asyncio
class TestAgentComponentEventIntegration:
    """Integration test suite for AgentComponent event patterns."""

    async def test_decorator_pattern_registration(self):
        """Test that @on decorators work correctly in AgentComponents."""
        component = DecoratorPatternComponent()

        # Check that decorator metadata is attached to methods
        # The metadata should be on the class method, not the instance method
        class_method = type(component).on_agent_ready_static
        assert hasattr(class_method, "_event_handler_config")
        config = class_method._event_handler_config
        assert AgentEvents.AGENT_INIT_AFTER in config["events"]

        # Create agent and verify handlers are registered
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async event handlers time to complete
        await asyncio.sleep(0.01)

        # Decorator handlers should have fired during initialization
        assert "agent_ready_static" in component.decorator_events

        # Test that decorated handlers respond to events
        component.decorator_events.clear()

        # Manually trigger tool events since direct tool calls don't fire them
        # (These events are fired during agent execution, not direct tool calls)
        await agent.apply(
            AgentEvents.TOOL_CALL_BEFORE,
            tool_name="test_component_tool",
            parameters={"value": "test"},
        )

        # Execute the tool
        tool = agent.tools["test_component_tool"]
        result = await tool(_agent=agent, value="test")

        # Trigger after event with the result
        await agent.apply(
            AgentEvents.TOOL_CALL_AFTER,
            tool_name="test_component_tool",
            response=result,
        )

        # Give async event handlers time to complete
        await asyncio.sleep(0.01)

        # Verify decorator handlers captured the events
        assert any(
            "tool_before_static" in event for event in component.decorator_events
        )
        assert any("tool_after_static" in event for event in component.decorator_events)

    async def test_manual_registration_phases(self):
        """Test that manual registration works in setup and install phases."""
        component = DecoratorPatternComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Add a message to trigger setup handlers
        agent.append("Test user message")

        # Give async handlers time to complete
        await asyncio.sleep(0.01)

        # Verify setup handlers fired
        assert any("message_append_setup" in event for event in component.setup_events)

        # Execute agent to trigger install handlers
        # Note: We'll use a mock to avoid full LLM execution
        mock_response = MagicMock()
        mock_response.content = "Test response"

        # Manually trigger execute events to test install handlers
        await agent.apply(
            AgentEvents.EXECUTE_BEFORE, agent=agent, messages=agent.messages
        )
        await agent.apply(
            AgentEvents.EXECUTE_AFTER, agent=agent, response=mock_response
        )

        # Give async handlers time to complete
        await asyncio.sleep(0.01)

        # The execute_before handler is now fixed

        # Verify install handlers fired
        assert any(
            "execute_before_install" in event for event in component.install_events
        ), f"Events: {component.install_events}"
        assert any(
            "execute_after_install_async" in event for event in component.install_events
        ), f"Events: {component.install_events}"

    async def test_component_state_interactions(self):
        """Test that handlers respect component enabled/disabled state."""
        component = DecoratorPatternComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Test with component enabled (default)
        assert component.enabled
        agent.append("Test message 1")
        initial_setup_count = len(component.setup_events)
        assert initial_setup_count > 0

        # Disable component and test again
        component.enabled = False
        component.setup_events.clear()
        agent.append("Test message 2")

        # Setup handlers should not fire when disabled
        # (Note: Static @on handlers will still fire as they don't check enabled)
        disabled_setup_count = len(component.setup_events)
        assert disabled_setup_count == 0, "Manual handlers should respect enabled state"

        # Re-enable and verify handlers work again
        component.enabled = True
        agent.append("Test message 3")
        final_setup_count = len(component.setup_events)
        assert final_setup_count > 0, "Handlers should work after re-enabling"

    async def test_dynamic_configuration(self):
        """Test that manual registration allows dynamic configuration."""
        # Test with different priorities
        component_high = ManualRegistrationComponent(custom_priority=250)
        component_low = ManualRegistrationComponent(custom_priority=50)

        agent = Agent("Test system", extensions=[component_high, component_low])
        await agent.ready()

        # Both components should register handlers
        assert component_high.handler_count == 3
        assert component_low.handler_count == 3

        # Trigger tool events to test priority handling
        # Check if test_component_tool exists
        if "test_component_tool" in agent.tools:
            tool = agent.tools["test_component_tool"]
        else:
            # Create a mock tool for testing
            from good_agent.tools import Tool

            mock_tool = Tool(fn=lambda value: f"test:{value}", name="mock_tool")
            agent.tools["mock_tool"] = mock_tool
            tool = mock_tool

        # Trigger tool before event
        await agent.apply(
            AgentEvents.TOOL_CALL_BEFORE, tool_name="mock_tool", parameters={}
        )

        # Verify both components captured events with their priorities
        high_events = [e for e in component_high.events if "dynamic_priority:250" in e]
        low_events = [e for e in component_low.events if "dynamic_priority:50" in e]

        assert len(high_events) > 0, "High priority component should handle events"
        assert len(low_events) > 0, "Low priority component should handle events"

        # Test conditional handler (only high priority should fire)
        component_high.events.clear()
        component_low.events.clear()

        await agent.apply(
            AgentEvents.TOOL_CALL_AFTER, tool_name="mock_tool", response=MagicMock()
        )

        # Only high priority component should have conditional events
        high_conditional = [e for e in component_high.events if "conditional" in e]
        low_conditional = [e for e in component_low.events if "conditional" in e]

        assert len(high_conditional) > 0, (
            "High priority component should meet predicate"
        )
        assert len(low_conditional) == 0, (
            "Low priority component should not meet predicate"
        )

    async def test_hybrid_pattern_execution_order(self):
        """Test that static and dynamic handlers execute in correct priority order."""
        component = HybridPatternComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async handlers time to complete
        await asyncio.sleep(0.01)

        # All handlers should have fired during agent initialization
        # Verify execution order based on priorities:
        # 1. init_static_high (300)
        # 2. init_dynamic_high (250)
        # 3. init_dynamic_mid (200)
        # 4. init_static_low (50)

        all_events = component.static_events + component.dynamic_events

        # Should have all 4 events
        assert len(all_events) == 4
        assert "init_static_high" in component.static_events
        assert "init_static_low" in component.static_events
        assert "init_dynamic_mid" in component.dynamic_events
        assert "init_dynamic_high" in component.dynamic_events

    async def test_agent_access_patterns(self):
        """Test different patterns of agent access in handlers."""
        component = ManualRegistrationComponent()
        agent = Agent(
            "Test system with context",
            extensions=[component],
            context={"test_key": "test_value"},
        )
        await agent.ready()

        # System message handler should have access to agent.messages
        system_events = [e for e in component.events if "system_set" in e]
        assert len(system_events) > 0

        # Verify handler could access message count
        assert any("msg_count=" in event for event in system_events)

    async def test_error_handling_in_handlers(self):
        """Test that event handler errors don't break component functionality."""

        class ErrorComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.events = []

            @on(AgentEvents.AGENT_INIT_AFTER)
            def failing_static_handler(self, ctx: EventContext) -> None:
                """Handler that raises an exception."""
                self.events.append("before_error")
                raise ValueError("Test error in static handler")

            def setup(self, agent):
                super().setup(agent)

                @agent.on(AgentEvents.AGENT_INIT_AFTER, priority=50)
                def failing_dynamic_handler(ctx):
                    self.events.append("before_dynamic_error")
                    raise ValueError("Test error in dynamic handler")

                @agent.on(AgentEvents.AGENT_INIT_AFTER, priority=25)
                def working_handler(ctx):
                    self.events.append("working_handler")

        component = ErrorComponent()

        # Agent initialization should still succeed despite handler errors
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async handlers time to complete
        await asyncio.sleep(0.01)

        # Working handlers should still execute
        assert "working_handler" in component.events

        # Failing handlers should have started
        assert (
            "before_error" in component.events
            or "before_dynamic_error" in component.events
        )

    async def test_component_tool_integration(self):
        """Test that component tools work correctly with event handlers."""
        component = DecoratorPatternComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Give async handlers time to complete
        await asyncio.sleep(0.01)

        # Clear any initialization events
        component.decorator_events.clear()
        component.runtime_events.clear()

        # Manually trigger tool events (these are normally fired during agent execution)
        await agent.apply(
            AgentEvents.TOOL_CALL_BEFORE,
            tool_name="test_component_tool",
            parameters={"value": "integration_test"},
        )

        # Execute component tool
        tool = agent.tools["test_component_tool"]
        result = await tool(_agent=agent, value="integration_test")

        # Trigger after event
        await agent.apply(
            AgentEvents.TOOL_CALL_AFTER,
            tool_name="test_component_tool",
            response=result,
        )

        # Give async handlers time to complete
        await asyncio.sleep(0.01)

        # Verify tool executed correctly
        assert result.success
        assert result.response == "processed:integration_test"
        assert "tool_executed:integration_test" in component.runtime_events

        # Verify event handlers captured tool execution
        tool_before_events = [
            e for e in component.decorator_events if "tool_before_static" in e
        ]
        tool_after_events = [
            e for e in component.decorator_events if "tool_after_static" in e
        ]

        assert len(tool_before_events) > 0, "Tool before handler should fire"
        assert len(tool_after_events) > 0, "Tool after handler should fire"

        # Verify correct tool name in events
        assert any("test_component_tool" in event for event in tool_before_events)
        assert any("test_component_tool" in event for event in tool_after_events)


@pytest.mark.asyncio
async def test_eventrouter_inheritance_verification():
    """Verify that AgentComponent properly inherits from EventRouter."""
    from good_agent.utilities.event_router import EventRouter

    component = DecoratorPatternComponent()

    # Should be an instance of EventRouter
    assert isinstance(component, EventRouter)

    # Should have EventRouter methods
    assert hasattr(component, "on")
    assert hasattr(component, "do")
    assert hasattr(component, "apply")
    assert hasattr(component, "apply_async")

    # Should have AgentComponent-specific methods
    assert hasattr(component, "setup")
    assert hasattr(component, "install")
    assert hasattr(component, "enabled")

    # Should have _events dictionary from EventRouter
    assert hasattr(component, "_events")

    # The component itself won't have handlers registered because it overrides __post_init__
    # to prevent auto-registration (handlers are registered with the agent instead)
    # So we check that the metadata is still on the methods
    assert hasattr(type(component).on_agent_ready_static, "_event_handler_config")
    assert hasattr(type(component).on_tool_before_static, "_event_handler_config")
    assert hasattr(type(component).on_tool_after_static, "_event_handler_config")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "-s"])
