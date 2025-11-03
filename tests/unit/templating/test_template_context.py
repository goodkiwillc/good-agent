import asyncio

import pytest
from good_agent import Agent, global_context_provider
from good_agent.messages import UserMessage


class TestTemplateContext:
    """Test the template and context system"""

    def test_basic_context(self):
        """Test basic context on agent"""
        agent = Agent(
            "System prompt", context={"location": "New York", "unit": "Celsius"}
        )

        assert agent.context["location"] == "New York"
        assert agent.context["unit"] == "Celsius"

    def test_context_manager(self):
        """Test temporary context override"""
        agent = Agent(
            "System prompt", context={"location": "New York", "unit": "Celsius"}
        )

        # Test original context
        assert agent.context["location"] == "New York"

        # Test temporary override
        with agent.context(location="London", temp=20):
            assert agent.context["location"] == "London"
            assert agent.context["unit"] == "Celsius"  # Not overridden
            assert agent.context["temp"] == 20  # New value

        # Test context restored
        assert agent.context["location"] == "New York"
        assert "temp" not in agent.context

    def test_message_context(self):
        """Test message-level context"""
        Agent("System prompt", context={"location": "New York"})

        # Create message with template and context
        msg = UserMessage(
            content="",
            raw_content="Weather in {{location}} is {{temp}}°",
            context={"location": "London", "temp": 15},
        )

        assert msg.raw_content == "Weather in {{location}} is {{temp}}°"
        assert msg.context == {"location": "London", "temp": 15}
        # Note: Full rendering not yet implemented

    def test_global_context_provider(self):
        """Test global context provider registration"""
        # Save existing global providers
        from good_agent.templating import _GLOBAL_CONTEXT_PROVIDERS

        # Save original state
        original_providers = _GLOBAL_CONTEXT_PROVIDERS.copy()

        try:
            # Clear for testing
            _GLOBAL_CONTEXT_PROVIDERS.clear()

            @global_context_provider("test_value")
            def provide_test_value():
                return "global_test"

            # Verify registration
            assert "test_value" in _GLOBAL_CONTEXT_PROVIDERS
            assert _GLOBAL_CONTEXT_PROVIDERS["test_value"]() == "global_test"
        finally:
            # Restore original providers
            _GLOBAL_CONTEXT_PROVIDERS.clear()
            _GLOBAL_CONTEXT_PROVIDERS.update(original_providers)

    @pytest.mark.asyncio
    async def test_instance_context_provider(self):
        """Test instance-specific context provider"""
        agent = Agent("System prompt")

        counter = {"value": 0}

        @agent.context_provider("counter")
        def provide_counter():
            counter["value"] += 1
            return counter["value"]

        # Test provider is registered
        assert "counter" in agent.template._context_providers

        # Test async provider
        @agent.context_provider("async_time")
        async def provide_time():
            await asyncio.sleep(0.01)  # Simulate async work
            return "2024-01-01T12:00:00"

        # Resolve context with providers
        resolved = await agent.template.resolve_context(
            {"base": "value"}, {"override": "value2"}
        )

        assert resolved["base"] == "value"
        assert resolved["override"] == "value2"
        assert resolved["counter"] == 1
        assert resolved["async_time"] == "2024-01-01T12:00:00"

    def test_context_hierarchy(self):
        """Test context resolution hierarchy"""
        agent = Agent("System prompt", context={"a": 1, "b": 2, "c": 3})

        # Test base context
        assert agent.context["a"] == 1
        assert agent.context["b"] == 2
        assert agent.context["c"] == 3

        # Test temporary override
        with agent.context(a=10, d=4):
            assert agent.context["a"] == 10
            assert agent.context["b"] == 2
            assert agent.context["c"] == 3
            assert agent.context["d"] == 4

            # Test nested override
            with agent.context(b=20, e=5):
                assert agent.context["a"] == 10  # From parent override
                assert agent.context["b"] == 20  # From this override
                assert agent.context["c"] == 3  # From base
                assert agent.context["d"] == 4  # From parent override
                assert agent.context["e"] == 5  # From this override

    def test_template_rendering(self):
        """Test basic template rendering"""
        # Use core template rendering directly without agent dependencies
        from good_agent.templating import render_template

        # Test simple template
        result = render_template("Hello {{name}}!", {"name": "World"})
        assert result == "Hello World!"

        # Test multiple variables
        result = render_template(
            "{{greeting}} {{name}}, temp is {{temp}}°{{unit}}",
            {"greeting": "Hi", "name": "Alice", "temp": 25, "unit": "C"},
        )
        assert result == "Hi Alice, temp is 25°C"

    @pytest.mark.asyncio
    async def test_context_resolution_priority(self):
        """Test that context resolution follows correct priority"""
        from good_agent.templating import _GLOBAL_CONTEXT_PROVIDERS

        # Save original state
        original_providers = _GLOBAL_CONTEXT_PROVIDERS.copy()

        try:
            _GLOBAL_CONTEXT_PROVIDERS.clear()

            # Set up global provider
            @global_context_provider("priority_test")
            def global_provider():
                return "global"

            async with Agent(
                "System prompt", context={"priority_test": "agent"}
            ) as agent:
                # Set up instance provider
                @agent.context_provider("priority_test")
                def instance_provider():
                    return "instance"

                # Test resolution - agent context should win over providers
                resolved = await agent.template.resolve_context(
                    agent.context.as_dict(), None
                )
                assert resolved["priority_test"] == "agent"

                # Test with message context - should override everything
                resolved = await agent.template.resolve_context(
                    agent.context.as_dict(), {"priority_test": "message"}
                )
                assert resolved["priority_test"] == "message"
        finally:
            # Restore original providers
            _GLOBAL_CONTEXT_PROVIDERS.clear()
            _GLOBAL_CONTEXT_PROVIDERS.update(original_providers)
