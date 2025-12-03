from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from good_agent import Agent
from good_agent.tools import ToolRegistry, tool


class TestAgentToolRegistryIntegration:
    """Test integration between Agent and Tool Registry"""

    @pytest_asyncio.fixture
    async def clean_registry(self):
        """Create a clean registry for each test"""
        # Reset global registry
        import good_agent.tools.registry

        good_agent.tools.registry._global_registry = None

        registry = ToolRegistry()
        await registry.initialize(load_entry_points=False)

        # Set as global
        good_agent.tools.registry._global_registry = registry

        return registry

    def setup_method(self):
        """Reset global state before each test"""
        import good_agent.tools.registry

        good_agent.tools.registry._global_registry = None

    @pytest.mark.asyncio
    async def test_agent_with_tool_patterns(self, clean_registry):
        """Test agent creation with tool patterns"""
        registry = clean_registry

        # Create mock tools and register them
        @tool
        def get_weather(location: str) -> str:
            """Get weather for a location"""
            return f"Weather in {location}"

        @tool
        def get_forecast(location: str, days: int = 3) -> str:
            """Get weather forecast"""
            return f"Forecast for {location} ({days} days)"

        # Register tools with tags
        await registry.register("get_weather", get_weather, tags=["weather", "api"])
        await registry.register("get_forecast", get_forecast, tags=["weather", "forecast"])

        # Create agent with tool patterns
        async with Agent("You are a weather assistant", tools=["weather:*"]) as agent:
            # Agent is already ready due to __aenter__ calling initialize()

            # Verify tools were loaded
            assert "get_weather" in agent.tools
            assert "get_forecast" in agent.tools

    @pytest.mark.asyncio
    async def test_agent_with_specific_tool_names(self, clean_registry):
        """Test agent creation with specific tool names"""
        registry = clean_registry

        @tool
        def calculate(expression: str) -> str:
            """Calculate a mathematical expression"""
            return f"Result: {expression}"

        @tool
        def convert_units(value: float, from_unit: str, to_unit: str) -> str:
            """Convert between units"""
            return f"{value} {from_unit} = ? {to_unit}"

        await registry.register("calculate", calculate, tags=["math"])
        await registry.register("convert_units", convert_units, tags=["math", "conversion"])

        # Create agent with specific tool name
        async with Agent("You are a math assistant", tools=["calculate"]) as agent:
            # Agent is already ready from async context manager

            # Only the specific tool should be loaded
            assert "calculate" in agent.tools
            assert "convert_units" not in agent.tools

    @pytest.mark.asyncio
    async def test_agent_with_mixed_tool_types(self, clean_registry):
        """Test agent with mix of patterns, names, and direct functions"""
        registry = clean_registry

        # Register a tool in registry
        @tool
        def registered_tool() -> str:
            """A tool registered in the registry"""
            return "from registry"

        await registry.register("registered_tool", registered_tool, tags=["registry"])

        # Create a direct function tool
        def direct_function(message: str) -> str:
            """A direct function tool"""
            return f"Direct: {message}"

        # Create agent with mixed tools
        async with Agent(
            "You are a versatile assistant",
            tools=[
                "registry:*",  # Pattern from registry
                "registered_tool",  # Specific name from registry
                direct_function,  # Direct function
            ],
        ) as agent:
            # Agent is already ready from async context manager

            # Verify all tools are available
            assert "registered_tool" in agent.tools
            assert "direct_function" in agent.tools

    @pytest.mark.asyncio
    async def test_agent_tools_property_access(self, clean_registry):
        """Test accessing tools via agent.tools[name] as shown in spec"""
        registry = clean_registry

        @tool
        def test_tool(param: str) -> str:
            """Test tool with parameter"""
            return f"Result: {param}"

        await registry.register("test_tool", test_tool, tags=["test"])

        async with Agent("Test", tools=["test_tool"]) as agent:
            # Agent is already ready from async context manager

            # Test spec behavior: agent.tools["tool_name"]
            retrieved_tool = agent.tools["test_tool"]
            assert retrieved_tool is test_tool

            # Test spec behavior: modifying tool properties
            # agent.tools["test_tool"].description = "Custom description"
            agent.tools["test_tool"].description = "Custom description"
            assert agent.tools["test_tool"].description == "Custom description"

    @pytest.mark.asyncio
    async def test_agent_tool_pattern_wildcard(self, clean_registry):
        """Test wildcard pattern matching"""
        registry = clean_registry

        # Register tools with various tags
        @tool
        def weather_tool() -> str:
            return "weather"

        @tool
        def api_tool() -> str:
            return "api"

        @tool
        def util_tool() -> str:
            return "util"

        await registry.register("weather_tool", weather_tool, tags=["weather"])
        await registry.register("api_tool", api_tool, tags=["api"])
        await registry.register("util_tool", util_tool, tags=["util"])

        # Create agent with wildcard - should get all tools
        async with Agent("Test", tools=["*"]) as agent:
            # Agent is already ready from async context manager

            assert "weather_tool" in agent.tools
            assert "api_tool" in agent.tools
            assert "util_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_tool_priority_system(self, clean_registry):
        """Test that tool priority affects agent tool loading"""
        registry = clean_registry

        @tool
        def low_priority_tool() -> str:
            return "low priority"

        @tool
        def high_priority_tool() -> str:
            return "high priority"

        # Register same tool name with different priorities
        await registry.register("priority_tool", low_priority_tool, priority=1)
        await registry.register("priority_tool", high_priority_tool, priority=2)

        async with Agent("Test", tools=["priority_tool"]) as agent:
            # Agent is already ready from async context manager

            # Should get the high priority tool
            assert agent.tools["priority_tool"] is high_priority_tool

    @pytest.mark.asyncio
    async def test_tool_not_found_handling(self, clean_registry):
        """Test behavior when requested tool is not found"""
        async with Agent("Test", tools=["nonexistent_tool"]) as agent:
            # Agent is already ready from async context manager

            # Tool should not be in agent.tools
            assert "nonexistent_tool" not in agent.tools

            # Accessing non-existent tool should raise KeyError (spec behavior)
            with pytest.raises(KeyError):
                _ = agent.tools["nonexistent_tool"]

    @pytest.mark.asyncio
    async def test_entry_point_loading(self, clean_registry):
        """Test that entry points can be loaded if available"""
        registry = clean_registry

        # Mock entry points
        mock_entry_point = MagicMock()
        mock_entry_point.name = "weather:mock_weather_tool"
        mock_entry_point.load.return_value = lambda: MagicMock()

        with patch("importlib.metadata.entry_points") as mock_eps:
            mock_eps.return_value.select.return_value = [mock_entry_point]

            # Re-initialize registry to load entry points
            await registry._load_entry_points()

            # Create agent with pattern matching entry point
            async with Agent("Test", tools=["weather:*"]) as agent:
                # Agent is already ready from async context manager

                # Tool from entry point should be available
                assert "mock_weather_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_agent_tool_registry_isolation(self, clean_registry):
        """Test that different agents can have different tool sets"""
        registry = clean_registry

        @tool
        def shared_tool() -> str:
            return "shared"

        @tool
        def weather_tool() -> str:
            return "weather"

        @tool
        def math_tool() -> str:
            return "math"

        await registry.register("shared_tool", shared_tool, tags=["shared"])
        await registry.register("weather_tool", weather_tool, tags=["weather"])
        await registry.register("math_tool", math_tool, tags=["math"])

        # Create agents with different tool patterns
        async with (
            Agent("Weather assistant", tools=["weather:*", "shared_tool"]) as weather_agent,
            Agent("Math assistant", tools=["math:*", "shared_tool"]) as math_agent,
        ):
            # Agent is already ready from async context manager

            # Weather agent should have weather and shared tools
            assert "weather_tool" in weather_agent.tools
            assert "shared_tool" in weather_agent.tools
            assert "math_tool" not in weather_agent.tools

            # Math agent should have math and shared tools
            assert "math_tool" in math_agent.tools
            assert "shared_tool" in math_agent.tools
            assert "weather_tool" not in math_agent.tools

    @pytest.mark.asyncio
    async def test_sync_tool_registration(self, clean_registry):
        """Test synchronous tool registration for convenience"""
        # Note: This test demonstrates sync registration, but must run in async context
        # to avoid event loop conflicts

        # Create agent in async context
        async with Agent("Test") as agent:

            @tool
            def sync_tool_fn() -> str:
                return "sync"

            # sync_tool_fn is now a Tool instance after decoration
            sync_tool = sync_tool_fn

            # In a real sync context (outside pytest), register_tool_sync would work
            # But in our test environment, we need to use the async version
            await agent.tools.register_tool(sync_tool, name="sync_tool", tags=["sync"])

            assert "sync_tool" in agent.tools
            assert agent.tools["sync_tool"] is sync_tool

    @pytest.mark.asyncio
    async def test_spec_example_workflow(self, clean_registry):
        """Test the exact workflow shown in the spec"""
        registry = clean_registry

        # This replicates the spec example
        def get_weather(location: str) -> str:
            """Get the current weather for a given location."""
            return f"The weather in {location} is sunny and 72°F"

        # Register tool globally (as would happen via entry points or manual registration)
        get_weather_tool = tool(get_weather)
        await registry.register("get_weather", get_weather_tool, tags=["weather"])

        # Create agent as shown in spec
        async with Agent(
            "You are a helpful assistant.",
            model="gpt-4.1-mini",
            tools=["get_weather"],  # Use already registered tool by name
        ) as agent:
            # Agent is already ready from async context manager

            # Test spec behavior: agent.tools["get_weather"]
            assert "get_weather" in agent.tools

            # Test spec behavior: accessing tool properties
            tool_instance = agent.tools["get_weather"]
            assert tool_instance.description == "Get the current weather for a given location."

            # Test spec behavior: modifying tool properties
            agent.tools["get_weather"].description = "Get the current weather for a given location."
            assert (
                agent.tools["get_weather"].description
                == "Get the current weather for a given location."
            )

    @pytest.mark.asyncio
    async def test_tag_wildcard_spec_example(self, clean_registry):
        """Test the tag wildcard example from the spec"""
        registry = clean_registry

        # Register multiple weather tools
        @tool
        def get_weather() -> str:
            return "current weather"

        @tool
        def get_forecast() -> str:
            return "weather forecast"

        @tool
        def weather_alerts() -> str:
            return "weather alerts"

        await registry.register("get_weather", get_weather, tags=["weather"])
        await registry.register("get_forecast", get_forecast, tags=["weather", "forecast"])
        await registry.register("weather_alerts", weather_alerts, tags=["weather", "alerts"])

        # Test spec example: tools=["weather:*"]
        async with Agent(
            "You are a helpful assistant.",
            model="gpt-4.1-mini",
            tools=["weather:*"],  # Use all tools with tag "weather"
        ) as agent:
            # Agent is already ready from async context manager

            # All weather tools should be loaded
            assert "get_weather" in agent.tools
            assert "get_forecast" in agent.tools
            assert "weather_alerts" in agent.tools
