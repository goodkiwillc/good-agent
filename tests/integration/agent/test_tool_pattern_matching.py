import pytest
import pytest_asyncio
from good_agent import Agent
from good_agent.tools import Tool, get_tool_registry


@pytest_asyncio.fixture
async def setup_test_tools():
    """Set up test tools with tags"""
    # Clear the global registry to avoid conflicts
    import good_agent.tools.registry

    good_agent.tools.registry._global_registry = None

    # Get registry
    registry = await get_tool_registry()

    # Create weather tools
    @Tool
    def get_current_weather(location: str) -> str:
        """Get current weather for a location"""
        return f"Weather in {location}: Sunny, 72°F"

    @Tool
    def get_weather_forecast(location: str, days: int = 7) -> str:
        """Get weather forecast for a location"""
        return f"{days}-day forecast for {location}: Mostly sunny"

    # Create calculation tools
    @Tool
    def calculate_sum(a: float, b: float) -> float:
        """Calculate sum of two numbers"""
        return a + b

    @Tool
    def calculate_product(a: float, b: float) -> float:
        """Calculate product of two numbers"""
        return a * b

    # Register with tags
    await registry.register(
        "get_current_weather", get_current_weather, tags=["weather", "api"]
    )
    await registry.register(
        "get_weather_forecast", get_weather_forecast, tags=["weather", "api"]
    )
    await registry.register(
        "calculate_sum", calculate_sum, tags=["math", "calculation"]
    )
    await registry.register(
        "calculate_product", calculate_product, tags=["math", "calculation"]
    )

    return registry


class TestToolPatternMatching:
    """Test pattern-based tool selection"""

    @pytest.mark.asyncio
    async def test_tag_wildcard_pattern(self, setup_test_tools):
        """Test selecting all tools with a specific tag using tag:* pattern"""
        # Create agent with weather:* pattern
        agent = Agent("You are a weather assistant", tools=["weather:*"])

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Check that only weather tools are loaded
        assert len(agent.tools) == 2
        assert "get_current_weather" in agent.tools
        assert "get_weather_forecast" in agent.tools
        assert "calculate_sum" not in agent.tools
        assert "calculate_product" not in agent.tools

    @pytest.mark.asyncio
    async def test_multiple_patterns(self, setup_test_tools):
        """Test using multiple patterns"""
        # Create agent with multiple patterns
        agent = Agent(
            "You are a multi-purpose assistant", tools=["weather:*", "calculate_sum"]
        )

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Check that weather tools and calculate_sum are loaded
        assert len(agent.tools) == 3
        assert "get_current_weather" in agent.tools
        assert "get_weather_forecast" in agent.tools
        assert "calculate_sum" in agent.tools
        assert "calculate_product" not in agent.tools

    @pytest.mark.asyncio
    async def test_specific_tag_tool_pattern(self, setup_test_tools):
        """Test selecting specific tool with tag using tag:tool_name pattern"""
        # Create agent with specific tag:tool pattern
        agent = Agent(
            "You are a weather assistant", tools=["weather:get_current_weather"]
        )

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Check that only the specific tool is loaded
        assert len(agent.tools) == 1
        assert "get_current_weather" in agent.tools
        assert "get_weather_forecast" not in agent.tools

    @pytest.mark.asyncio
    async def test_all_tools_pattern(self, setup_test_tools):
        """Test selecting all tools using * pattern"""
        # Create agent with * pattern
        agent = Agent("You are a universal assistant", tools=["*"])

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Check that all tools are loaded
        assert len(agent.tools) == 4
        assert "get_current_weather" in agent.tools
        assert "get_weather_forecast" in agent.tools
        assert "calculate_sum" in agent.tools
        assert "calculate_product" in agent.tools

    @pytest.mark.asyncio
    async def test_exact_name_pattern(self, setup_test_tools):
        """Test selecting tool by exact name"""
        # Create agent with exact tool names
        agent = Agent(
            "You are a calculation assistant",
            tools=["calculate_sum", "calculate_product"],
        )

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Check that only specified tools are loaded
        assert len(agent.tools) == 2
        assert "calculate_sum" in agent.tools
        assert "calculate_product" in agent.tools
        assert "get_current_weather" not in agent.tools
        assert "get_weather_forecast" not in agent.tools

    @pytest.mark.asyncio
    async def test_mixed_patterns_and_instances(self, setup_test_tools):
        """Test mixing pattern strings with direct tool instances"""

        # Create a direct tool
        @Tool
        def custom_tool(input: str) -> str:
            """A custom tool"""
            return f"Custom: {input}"

        # Create agent with mixed tools
        agent = Agent("You are a mixed assistant", tools=["weather:*", custom_tool])

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Check that pattern tools and direct tool are loaded
        assert len(agent.tools) == 3
        assert "get_current_weather" in agent.tools
        assert "get_weather_forecast" in agent.tools
        assert "custom_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_nonexistent_pattern(self, setup_test_tools):
        """Test that nonexistent patterns don't load any tools"""
        # Create agent with nonexistent pattern
        agent = Agent("You are an assistant", tools=["nonexistent:*", "fake_tool"])

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Check that no tools are loaded
        assert len(agent.tools) == 0

    @pytest.mark.asyncio
    async def test_tool_execution_with_patterns(self, setup_test_tools):
        """Test that pattern-loaded tools can be executed"""
        # Create agent with weather tools
        agent = Agent("You are a weather assistant", tools=["weather:*"])

        # Wait for agent to be ready (tools will be loaded)
        await agent.ready()

        # Execute a tool
        response = await agent.invoke("get_current_weather", location="New York")

        # Check execution worked
        assert response.success
        assert response.response == "Weather in New York: Sunny, 72°F"
        assert response.tool_name == "get_current_weather"
