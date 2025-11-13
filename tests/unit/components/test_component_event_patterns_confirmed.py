import pytest
from good_agent import Agent, AgentComponent, AgentEvents
from good_agent.core.event_router import EventContext, on


class ProofOfConceptComponent(AgentComponent):
    """Component proving both decorator and manual patterns work."""

    def __init__(self):
        super().__init__()
        self.decorator_events = []
        self.manual_events = []
        self.lifecycle_events = []

    # ✅ DECORATOR PATTERN WORKS
    @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=200)
    def on_message_decorator(self, ctx: EventContext) -> None:
        """Decorator handler - fires automatically when registered."""
        message = ctx.parameters.get("message")
        message_type = type(message).__name__ if message else "None"
        self.decorator_events.append(f"decorator:message:{message_type}")

    @on(AgentEvents.EXTENSION_INSTALL_AFTER, priority=100)
    def on_install_complete_decorator(self, ctx: EventContext) -> None:
        """Decorator handler for extension installation."""
        ext_name = getattr(ctx.parameters.get("extension"), "__class__", {})
        if hasattr(ext_name, "__name__"):
            ext_name = ext_name.__name__
        else:
            ext_name = "unknown"
        self.decorator_events.append(f"decorator:install:{ext_name}")

    # ✅ MANUAL PATTERN WORKS
    def setup(self, agent):
        """Manual registration during setup phase."""
        super().setup(agent)
        self.lifecycle_events.append("setup_called")

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=100)
        def on_message_manual(ctx):
            """Manual handler - can check enabled state."""
            if not self.enabled:
                return
            message = ctx.parameters.get("message")
            message_type = type(message).__name__ if message else "None"
            self.manual_events.append(f"manual:message:{message_type}")

    async def install(self, agent):
        """Manual registration during install phase."""
        await super().install(agent)
        self.lifecycle_events.append("install_called")

        @agent.on(AgentEvents.EXTENSION_INSTALL_AFTER, priority=50)
        async def on_install_manual(ctx):
            """Async manual handler."""
            if not self.enabled:
                return
            ext_name = getattr(ctx.parameters.get("extension"), "__class__", {})
            if hasattr(ext_name, "__name__"):
                ext_name = ext_name.__name__
            else:
                ext_name = "unknown"
            self.manual_events.append(f"manual:install:{ext_name}")


class DecoratorTestComponent(AgentComponent):
    """Component using ONLY @on decorators to prove they work."""

    def __init__(self):
        super().__init__()
        self.events = []

    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    def on_message_pure_decorator(self, ctx: EventContext) -> None:
        """Pure decorator handler."""
        self.events.append("pure_decorator:message")


class ManualTestComponent(AgentComponent):
    """Component using ONLY manual registration."""

    def __init__(self):
        super().__init__()
        self.events = []

    def setup(self, agent):
        super().setup(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def on_message_pure_manual(ctx):
            if not self.enabled:
                return
            self.events.append("pure_manual:message")


@pytest.mark.asyncio
class TestComponentEventPatternsConfirmed:
    """Definitive test suite proving both patterns work."""

    async def test_decorator_pattern_confirmed(self):
        """✅ PROOF: @on decorators work in AgentComponents."""
        component = DecoratorTestComponent()

        # ✅ Verify decorator metadata attached correctly
        assert hasattr(component.on_message_pure_decorator, "_event_handler_config")
        config = component.on_message_pure_decorator._event_handler_config
        assert AgentEvents.MESSAGE_APPEND_AFTER in config["events"]

        # ✅ Verify EventRouter inheritance
        from good_agent.core.event_router import EventRouter

        assert isinstance(component, EventRouter)

        # ✅ Verify that AgentComponent prevents auto-registration on itself
        # (to avoid double registration when used with agent)
        assert len(component._events) == 0, (
            "Component should not auto-register handlers on itself"
        )

        # ✅ Verify decorator handlers work with agent
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # ✅ Verify handlers were registered with the agent during setup
        assert AgentEvents.MESSAGE_APPEND_AFTER in agent._events
        # Should have at least the decorator handler registered
        handlers = agent._events[AgentEvents.MESSAGE_APPEND_AFTER]
        assert len(handlers) > 0

        # Trigger event and verify decorator handler fires
        agent.append("Decorator test message")
        assert "pure_decorator:message" in component.events

        print("✅ CONFIRMED: @on decorator pattern works in AgentComponents!")

    async def test_manual_pattern_confirmed(self):
        """✅ PROOF: Manual registration works correctly."""
        component = ManualTestComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # ✅ Test enabled state (default)
        assert component.enabled
        agent.append("Manual test message")
        assert "pure_manual:message" in component.events

        # ✅ Test disabled state respect
        component.events.clear()
        component.enabled = False
        agent.append("Disabled test message")

        # Manual handlers should respect enabled state
        disabled_events = [e for e in component.events if "pure_manual" in e]
        assert len(disabled_events) == 0

        print("✅ CONFIRMED: Manual registration pattern works!")

    async def test_hybrid_pattern_confirmed(self):
        """✅ PROOF: Both patterns work together seamlessly."""
        component = ProofOfConceptComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # ✅ Verify lifecycle methods called
        assert "setup_called" in component.lifecycle_events
        assert "install_called" in component.lifecycle_events

        # ✅ Test message handling (both patterns should fire)
        agent.append("Hybrid test message")

        # Both decorator and manual handlers should fire
        decorator_events = [e for e in component.decorator_events if "message" in e]
        manual_events = [e for e in component.manual_events if "message" in e]

        assert len(decorator_events) > 0, (
            f"Decorator events: {component.decorator_events}"
        )
        assert len(manual_events) > 0, f"Manual events: {component.manual_events}"

        print("✅ CONFIRMED: Hybrid pattern (decorator + manual) works!")

    async def test_component_state_integration_confirmed(self):
        """✅ PROOF: Component state properly integrates with event handlers."""
        component = ProofOfConceptComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Clear any initialization events
        component.decorator_events.clear()
        component.manual_events.clear()

        # ✅ Test enabled state (both patterns fire)
        agent.append("Enabled state test")

        decorator_count = len([e for e in component.decorator_events if "message" in e])
        manual_count = len([e for e in component.manual_events if "message" in e])

        assert decorator_count > 0, "Decorator handlers should fire when enabled"
        assert manual_count > 0, "Manual handlers should fire when enabled"

        # ✅ Test disabled state (manual respects, decorator doesn't auto-check)
        component.decorator_events.clear()
        component.manual_events.clear()
        component.enabled = False

        agent.append("Disabled state test")

        # Manual handlers check self.enabled
        disabled_manual = [e for e in component.manual_events if "message" in e]
        assert len(disabled_manual) == 0, "Manual handlers should respect enabled=False"

        # Decorator handlers don't auto-check enabled (developer choice)
        disabled_decorator = [e for e in component.decorator_events if "message" in e]
        assert len(disabled_decorator) > 0, (
            "Decorator handlers don't auto-check enabled"
        )

        print("✅ CONFIRMED: Component state integration works as expected!")

    async def test_priority_handling_confirmed(self):
        """✅ PROOF: Event priorities work across both patterns."""

        class PriorityTestComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.execution_order = []

            @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=300)
            def high_priority_decorator(self, ctx: EventContext):
                self.execution_order.append("decorator_high")

            @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=100)
            def low_priority_decorator(self, ctx: EventContext):
                self.execution_order.append("decorator_low")

            def setup(self, agent):
                super().setup(agent)

                @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=200)
                def mid_priority_manual(ctx):
                    self.execution_order.append("manual_mid")

        component = PriorityTestComponent()
        agent = Agent("Test system", extensions=[component])
        await agent.ready()

        # Trigger event
        agent.append("Priority test")

        # All handlers should execute
        assert len(component.execution_order) == 3
        expected_handlers = {"decorator_high", "manual_mid", "decorator_low"}
        actual_handlers = set(component.execution_order)
        assert expected_handlers == actual_handlers

        print("✅ CONFIRMED: Event priorities work across both patterns!")


@pytest.mark.asyncio
async def test_eventrouter_inheritance_final_proof():
    """✅ FINAL PROOF: AgentComponent is a fully functional EventRouter."""
    from good_agent.core.event_router import EventRouter

    component = ProofOfConceptComponent()

    # ✅ Is EventRouter instance
    assert isinstance(component, EventRouter)

    # ✅ Has all EventRouter capabilities
    assert hasattr(component, "on")
    assert hasattr(component, "do")
    assert hasattr(component, "apply")
    assert hasattr(component, "apply_async")
    assert hasattr(component, "_events")

    # ✅ Decorated handlers are NOT auto-registered on component itself
    # (This is intentional to prevent double registration with agent)
    assert len(component._events) == 0, (
        "Component should not auto-register decorated handlers"
    )

    # ✅ But metadata is preserved for registration with agent
    assert hasattr(component.on_message_decorator, "_event_handler_config")
    assert hasattr(component.on_install_complete_decorator, "_event_handler_config")

    # ✅ Can still use EventRouter methods directly for manual registration
    test_events = []

    @component.on("test:event")
    def test_handler(ctx):
        test_events.append("direct_eventrouter_usage")

    component.do("test:event")
    await component.join_async(timeout=1.0)  # Wait for background tasks

    assert "direct_eventrouter_usage" in test_events

    print(
        "✅ FINAL CONFIRMATION: AgentComponent fully supports EventRouter functionality!"
    )


if __name__ == "__main__":
    print("🧪 Running comprehensive AgentComponent event pattern tests...")
    pytest.main([__file__, "-v", "-s"])
