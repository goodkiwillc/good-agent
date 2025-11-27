from typing import Any, cast

import pytest
from good_agent import Agent, tool


class TestStatefulResourceBase:
    """Test suite for StatefulResource base class."""

    @pytest.mark.asyncio
    async def test_stateful_resource_exists(self):
        """Test that StatefulResource base class exists and is importable."""
        from good_agent.resources import StatefulResource

        assert StatefulResource is not None

    @pytest.mark.asyncio
    async def test_stateful_resource_is_abstract(self):
        """Test that StatefulResource cannot be instantiated directly."""
        from abc import ABC

        from good_agent.resources import StatefulResource

        # Check it's abstract
        assert issubclass(StatefulResource, ABC)

        # Cannot instantiate abstract class
        with pytest.raises(TypeError) as excinfo:
            cast(type[Any], StatefulResource)("test")

        assert "Can't instantiate abstract class" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_stateful_resource_has_required_methods(self):
        """Test that StatefulResource has required abstract methods."""
        from good_agent.resources import StatefulResource

        # Check for required abstract methods
        assert hasattr(StatefulResource, "initialize")
        assert hasattr(StatefulResource, "persist")
        assert hasattr(StatefulResource, "get_tools")

    @pytest.mark.asyncio
    async def test_stateful_resource_has_state_property(self):
        """Test that StatefulResource has state property with getter/setter."""
        from good_agent.resources import StatefulResource

        # Create concrete implementation for testing
        class TestResource(StatefulResource[str]):
            async def initialize(self):
                self.state = "initialized"

            async def persist(self):
                pass

            def get_tools(self):
                return {}

        resource = TestResource("test")

        # State should initially raise error if not set
        with pytest.raises(RuntimeError) as excinfo:
            _ = resource.state
        assert "not initialized" in str(excinfo.value).lower()

        # Should be able to set state
        resource.state = "test value"
        assert resource.state == "test value"

    @pytest.mark.asyncio
    async def test_stateful_resource_context_manager(self):
        """Test that StatefulResource works as async context manager with agent."""
        from good_agent.resources import StatefulResource

        # Create concrete implementation
        class TestResource(StatefulResource[str]):
            async def initialize(self):
                self.state = "initialized"

            async def persist(self):
                self._persisted = True

            def get_tools(self):
                @tool
                async def test_tool() -> str:
                    return "test"

                return {"test_tool": test_tool}

        resource = TestResource("test_resource")

        async with Agent("Test agent") as agent:
            # Store original tools
            original_tools = list(agent.tools.keys())

            # Use resource as context manager
            async with resource(agent) as res:
                # Should return self
                assert res is resource

                # Should be initialized
                assert resource.state == "initialized"
                assert resource._initialized is True

                # Tools should be replaced
                assert "test_tool" in agent.tools
                # Original tools should not be present
                for orig_tool in original_tools:
                    assert orig_tool not in agent.tools

            # Original tools should be restored
            current_tools = list(agent.tools.keys())
            assert current_tools == original_tools

    @pytest.mark.asyncio
    async def test_stateful_resource_modifies_system_message(self):
        """Test that StatefulResource modifies system message in thread context."""
        from good_agent.resources import StatefulResource

        class TestResource(StatefulResource[str]):
            async def initialize(self):
                self.state = "init"

            async def persist(self):
                pass

            def get_tools(self):
                return {}

        resource = TestResource("doc")

        async with Agent("Original system prompt") as agent:
            # Track if thread_context was called
            context_called = False
            original_thread_context = agent._context_manager.thread_context

            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def mock_thread_context(truncate_at: int | None = None):
                nonlocal context_called
                context_called = True
                async with original_thread_context(truncate_at) as messages:
                    yield messages

            # Replace thread_context temporarily
            setattr(agent._context_manager, "thread_context", mock_thread_context)

            async with resource(agent):
                # thread_context should have been called
                assert context_called

            # Restore original
            setattr(agent._context_manager, "thread_context", original_thread_context)

    @pytest.mark.asyncio
    async def test_stateful_resource_only_initializes_once(self):
        """Test that StatefulResource only calls initialize once."""
        from good_agent.resources import StatefulResource

        class TestResource(StatefulResource[str]):
            def __init__(self, name: str):
                super().__init__(name)
                self.init_count = 0

            async def initialize(self):
                self.init_count += 1
                self.state = "initialized"

            async def persist(self):
                pass

            def get_tools(self):
                return {}

        resource = TestResource("test")

        async with Agent("Test") as agent:
            # First use
            async with resource(agent):
                assert resource.init_count == 1

            # Second use - should not re-initialize
            async with resource(agent):
                assert resource.init_count == 1

    @pytest.mark.asyncio
    async def test_stateful_resource_tools_are_converted_to_list(self):
        """Test that get_tools() dict is converted to list for agent.tools()."""
        from good_agent.resources import StatefulResource

        class TestResource(StatefulResource[str]):
            async def initialize(self):
                self.state = "init"

            async def persist(self):
                pass

            def get_tools(self):
                @tool
                async def read() -> str:
                    return "content"

                @tool
                async def write(text: str) -> str:
                    return f"wrote: {text}"

                return {"doc_read": read, "doc_write": write}

        resource = TestResource("doc")

        async with Agent("Test") as agent:
            async with resource(agent):
                # Tools should be available with their decorator names
                assert "read" in agent.tools
                assert "write" in agent.tools

                # Test they work
                read_tool = agent.tools["read"]
                result = await read_tool(_agent=agent)
                assert result.response == "content"

    @pytest.mark.asyncio
    async def test_stateful_resource_creates_context_prefix(self):
        """Test that _create_context_prefix generates proper edit context."""
        from good_agent.resources import StatefulResource

        class TestResource(StatefulResource[str]):
            async def initialize(self):
                self.state = "init"

            async def persist(self):
                pass

            def get_tools(self):
                return {}

        resource = TestResource("my_document")
        prefix = resource._create_context_prefix()

        # Should contain edit context markers
        assert "<|edit-context|>" in prefix
        assert "<|/edit-context|>" in prefix
        assert "my_document" in prefix
        assert "editing" in prefix.lower()

    @pytest.mark.asyncio
    async def test_stateful_resource_generic_type(self):
        """Test that StatefulResource properly handles generic type parameter."""
        from good_agent.resources import StatefulResource

        # Test with different state types
        class StringResource(StatefulResource[str]):
            async def initialize(self):
                self.state = "text"

            async def persist(self):
                pass

            def get_tools(self):
                return {}

        class DictResource(StatefulResource[dict]):
            async def initialize(self):
                self.state = {"key": "value"}

            async def persist(self):
                pass

            def get_tools(self):
                return {}

        str_resource = StringResource("str")
        dict_resource = DictResource("dict")

        str_resource.state = "test"
        assert str_resource.state == "test"

        dict_resource.state = {"new": "data"}
        assert dict_resource.state == {"new": "data"}
