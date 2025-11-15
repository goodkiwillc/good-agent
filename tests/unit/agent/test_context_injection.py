from unittest.mock import AsyncMock, Mock

import pytest
from good_agent import Agent
from good_agent.components.template_manager.injection import (
    CircularDependencyError,
    ContextProviderError,
    ContextResolver,
    ContextValue,
)


class TestContextValueDescriptor:
    """Test the ContextValue descriptor class."""

    def test_context_value_initialization_with_name(self):
        """Test ContextValue can be initialized with a name."""
        cv = ContextValue("test_value")
        assert cv.name == "test_value"
        assert cv.required is True
        assert cv.default is ContextValue._MISSING
        assert cv.default_factory is None

    def test_context_value_with_default(self):
        """Test ContextValue with a default value."""
        cv = ContextValue("test_value", default="default_value")
        assert cv.name == "test_value"
        assert cv.default == "default_value"
        assert cv.required is True

    def test_context_value_with_default_factory(self):
        """Test ContextValue with a default factory."""
        factory = Mock(return_value="factory_value")
        cv = ContextValue("test_value", default_factory=factory)
        assert cv.name == "test_value"
        assert cv.default_factory is factory
        assert cv.required is True

    def test_context_value_optional(self):
        """Test ContextValue with required=False."""
        cv = ContextValue("test_value", required=False)
        assert cv.name == "test_value"
        assert cv.required is False
        assert cv.default is ContextValue._MISSING

    def test_context_value_default_and_factory_exclusive(self):
        """Test that default and default_factory are mutually exclusive."""
        with pytest.raises(
            ValueError, match="Cannot specify both default and default_factory"
        ):
            ContextValue("test", default="value", default_factory=lambda: "other")


class TestContextResolver:
    """Test the ContextResolver class for circular dependency detection."""

    @pytest.fixture
    def resolver(self):
        """Create a ContextResolver instance."""
        template_manager = Mock()
        return ContextResolver(template_manager)

    @pytest.mark.asyncio
    async def test_simple_value_resolution(self, resolver):
        """Test resolving a simple context value."""
        base_context = {"key": "value"}
        result = await resolver.resolve_value("key", base_context)
        assert result == "value"

    @pytest.mark.asyncio
    async def test_cached_value_resolution(self, resolver):
        """Test that resolved values are cached."""
        base_context = {}
        provider = AsyncMock(return_value="cached_value")
        resolver.get_provider = Mock(return_value=provider)

        # First call
        result1 = await resolver.resolve_value("test", base_context)
        assert result1 == "cached_value"
        provider.assert_called_once()

        # Second call should use cache
        result2 = await resolver.resolve_value("test", base_context)
        assert result2 == "cached_value"
        provider.assert_called_once()  # Not called again

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, resolver):
        """Test that circular dependencies are detected."""
        base_context = {}

        # Setup circular providers
        async def provider_a():
            await resolver.resolve_value("b", base_context)
            return "a"

        async def provider_b():
            await resolver.resolve_value("a", base_context)
            return "b"

        def get_provider(name):
            if name == "a":
                return provider_a
            elif name == "b":
                return provider_b
            return None

        resolver.get_provider = get_provider

        with pytest.raises(CircularDependencyError) as exc_info:
            await resolver.resolve_value("a", base_context)

        assert "Circular dependency detected" in str(exc_info.value)
        assert "a -> b -> a" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_provider(self, resolver):
        """Test error when no provider exists for a context value."""
        resolver.get_provider = Mock(return_value=None)

        with pytest.raises(KeyError, match="No context provider for 'missing'"):
            await resolver.resolve_value("missing", {})

    @pytest.mark.asyncio
    async def test_provider_error_handling(self, resolver):
        """Test that provider errors are wrapped appropriately."""

        async def failing_provider():
            raise ValueError("Provider failed")

        resolver.get_provider = Mock(return_value=failing_provider)

        with pytest.raises(ContextProviderError) as exc_info:
            await resolver.resolve_value("failing", {})

        assert "Failed to execute context provider 'failing'" in str(exc_info.value)
        assert "Provider failed" in str(exc_info.value)


class TestFunctionInjectionModification:
    """Test modification of functions to support ContextValue injection."""

    def test_detect_context_value_parameters(self):
        """Test detection of ContextValue parameters in function signatures."""
        from good_agent.templating.injection import _get_context_params

        def test_func(
            regular: str,
            context_val: str = ContextValue("test"),
            with_default: int = ContextValue("num", default=5),
        ):
            pass

        context_params = _get_context_params(test_func)
        assert "context_val" in context_params
        assert "with_default" in context_params
        assert "regular" not in context_params

    def test_mixed_injection_types(self):
        """Test mixing ContextValue with Depends injection."""
        from fast_depends import Depends
        from good_agent.templating.injection import _get_injection_params

        # Create a dummy dependency provider
        def agent_provider():
            return Mock()

        def test_func(
            regular: str,
            agent: Agent = Depends(agent_provider),
            context_val: str = ContextValue("test"),
        ):
            pass

        depends_params, context_params = _get_injection_params(test_func)
        assert "agent" in depends_params
        assert "context_val" in context_params
        assert "regular" not in depends_params
        assert "regular" not in context_params


class TestContextInjectionIntegration:
    """Integration tests for context injection in tools and providers."""

    @pytest.mark.asyncio
    async def test_tool_with_context_injection(self):
        """Test that tools can receive context values."""
        from good_agent import tool

        @tool
        async def search(
            query: str,
            user_id: str = ContextValue("user_id"),
            region: str = ContextValue("region", default="US"),
        ) -> str:
            return f"Searching for {query} as user {user_id} in {region}"

        # Create agent with context
        agent = Agent("Test")
        agent.context["user_id"] = "123"

        # Invoke tool
        result = await agent.invoke(search, query="python")
        assert result.response == "Searching for python as user 123 in US"

    @pytest.mark.asyncio
    async def test_context_provider_with_dependencies(self):
        """Test context providers can depend on other context values."""
        agent = Agent("Test")

        @agent.context_provider("base_value")
        async def base_provider():
            return 10

        @agent.context_provider("derived_value")
        async def derived_provider(base: int = ContextValue("base_value")) -> int:
            return base * 2

        context = await agent.template.resolve_context({})
        assert context["base_value"] == 10
        assert context["derived_value"] == 20

    @pytest.mark.asyncio
    async def test_context_provider_with_agent_injection(self):
        """Test context providers can receive both Agent and context values."""
        agent = Agent("Test")
        agent.context["multiplier"] = 3

        @agent.context_provider("computed")
        async def provider(agent: Agent, mult: int = ContextValue("multiplier")) -> str:
            return f"Agent {agent.id} with multiplier {mult}"

        # Pass the agent's context as base context
        base_context = (
            agent.context.as_dict()
            if hasattr(agent.context, "as_dict")
            else {"multiplier": 3}
        )
        context = await agent.template.resolve_context(base_context)

        assert f"Agent {agent.id} with multiplier 3" in context["computed"]


class TestErrorHandling:
    """Test error handling in context injection."""

    @pytest.mark.asyncio
    async def test_missing_required_context_value(self):
        """Test error when required context value is missing."""
        from good_agent import tool

        @tool
        async def requires_value(data: str = ContextValue("required_data")) -> str:
            return data

        agent = Agent("Test")
        # Don't set the required context value

        # The tool should raise MissingContextValueError when invoked
        result = await agent.invoke(requires_value)

        # Check if the error is in the response
        assert result.success is False
        assert "MissingContextValueError" in str(
            result.error
        ) or "required_data" in str(result.error)

    @pytest.mark.asyncio
    async def test_optional_missing_context_value(self):
        """Test that optional context values return None when missing."""
        from good_agent import tool

        @tool
        async def optional_value(
            data: str | None = ContextValue("optional_data", required=False),
        ) -> str:
            return f"Data: {data}"

        agent = Agent("Test")
        result = await agent.invoke(optional_value)
        assert result.response == "Data: None"

    @pytest.mark.asyncio
    async def test_default_factory_error_handling(self):
        """Test error handling when default factory fails."""
        from good_agent import tool

        def failing_factory():
            raise ValueError("Factory failed")

        @tool
        async def uses_factory(
            data: str = ContextValue("missing", default_factory=failing_factory),
        ) -> str:
            return f"Data: {data}"

        agent = Agent("Test")
        # Don't set the value, so it falls back to factory

        # The factory should fail and propagate the error
        result = await agent.invoke(uses_factory)
        assert result.success is False
        assert "Factory failed" in str(result.error)
