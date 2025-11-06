import asyncio
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from good_agent.tools import (
    ToolRegistration,
    ToolRegistry,
    get_tool_registry,
    get_tool_registry_sync,
    register_tool,
)


class MockTool:
    """Mock tool for testing"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.version = "1.0.0"

    def __call__(self, *args, **kwargs):
        return f"Result from {self.name}"


class TestToolRegistration:
    """Test the ToolRegistration data class"""

    def test_tool_registration_creation(self):
        """Test creating a tool registration"""
        tool = MockTool("test_tool")
        reg = ToolRegistration(
            name="test_tool",
            tool=tool,
            tags={"weather", "api"},
            version="1.2.0",
            description="Test tool",
        )

        assert reg.name == "test_tool"
        assert reg.tool is tool
        assert reg.tags == {"weather", "api"}
        assert reg.version == "1.2.0"
        assert reg.description == "Test tool"
        assert reg.source == "manual"
        assert reg.priority == 0

    def test_matches_pattern_exact_name(self):
        """Test pattern matching with exact tool name"""
        tool = MockTool("weather_tool")
        reg = ToolRegistration(name="weather_tool", tool=tool, tags={"weather"})

        assert reg.matches_pattern("weather_tool") is True
        assert reg.matches_pattern("other_tool") is False

    def test_matches_pattern_wildcard(self):
        """Test pattern matching with wildcard"""
        tool = MockTool("any_tool")
        reg = ToolRegistration(name="any_tool", tool=tool)

        assert reg.matches_pattern("*") is True

    def test_matches_pattern_tag_wildcard(self):
        """Test pattern matching with tag:* format"""
        tool = MockTool("weather_tool")
        reg = ToolRegistration(name="weather_tool", tool=tool, tags={"weather", "api"})

        assert reg.matches_pattern("weather:*") is True
        assert reg.matches_pattern("api:*") is True
        assert reg.matches_pattern("nonexistent:*") is False

    def test_matches_pattern_tag_specific(self):
        """Test pattern matching with tag:name format"""
        tool = MockTool("get_weather")
        reg = ToolRegistration(name="get_weather", tool=tool, tags={"weather"})

        assert reg.matches_pattern("weather:get_weather") is True
        assert reg.matches_pattern("weather:other_tool") is False
        assert reg.matches_pattern("nonexistent:get_weather") is False

    def test_matches_pattern_no_colon(self):
        """Test pattern matching without colon (exact name match)"""
        tool = MockTool("simple_tool")
        reg = ToolRegistration(name="simple_tool", tool=tool, tags={"tag1"})

        assert reg.matches_pattern("simple_tool") is True
        assert reg.matches_pattern("other_tool") is False


class TestToolRegistry:
    """Test the ToolRegistry class"""

    @pytest_asyncio.fixture
    async def registry(self):
        """Create a fresh registry for each test"""
        reg = ToolRegistry()
        await reg.initialize(
            load_entry_points=False
        )  # Don't load entry points in tests
        return reg

    @pytest.mark.asyncio
    async def test_registry_initialization(self):
        """Test registry initialization"""
        registry = ToolRegistry()
        assert not registry._initialized

        await registry.initialize(load_entry_points=False)
        assert registry._initialized

        # Second initialization should be no-op
        await registry.initialize()
        assert registry._initialized

    @pytest.mark.asyncio
    async def test_register_tool(self, registry):
        """Test registering a tool"""
        tool = MockTool("test_tool", "A test tool")

        await registry.register(
            "test_tool",
            tool,
            tags=["weather", "test"],
            version="1.1.0",
            description="Custom description",
        )

        # Verify tool is registered
        retrieved = await registry.get("test_tool")
        assert retrieved is tool

        # Verify registration details
        reg = await registry.get_registration("test_tool")
        assert reg is not None
        assert reg.name == "test_tool"
        assert reg.tool is tool
        assert reg.tags == {"weather", "test"}
        assert reg.version == "1.1.0"
        assert reg.description == "Custom description"
        assert reg.source == "manual"

    @pytest.mark.asyncio
    async def test_register_duplicate_tool_conflict(self, registry):
        """Test registering duplicate tool name is silently ignored"""
        tool1 = MockTool("duplicate")
        tool2 = MockTool("duplicate")

        await registry.register("duplicate", tool1)

        # Should not raise an error, just log warning and return
        await registry.register("duplicate", tool2)

        # First tool should still be registered
        retrieved = await registry.get("duplicate")
        assert retrieved is tool1

    @pytest.mark.asyncio
    async def test_register_duplicate_tool_replace(self, registry):
        """Test replacing existing tool"""
        tool1 = MockTool("replaceable")
        tool2 = MockTool("replacement")

        await registry.register("replaceable", tool1)
        await registry.register("replaceable", tool2, replace=True)

        retrieved = await registry.get("replaceable")
        assert retrieved is tool2

    @pytest.mark.asyncio
    async def test_register_priority_system(self, registry):
        """Test priority-based conflict resolution"""
        tool_low = MockTool("priority_test")
        tool_high = MockTool("priority_test")

        # Register low priority first
        await registry.register("priority_test", tool_low, priority=1)

        # Higher priority should replace
        await registry.register("priority_test", tool_high, priority=2)
        retrieved = await registry.get("priority_test")
        assert retrieved is tool_high

        # Lower priority should be ignored
        tool_ignored = MockTool("priority_test")
        await registry.register("priority_test", tool_ignored, priority=0)
        retrieved = await registry.get("priority_test")
        assert retrieved is tool_high  # Still the high priority tool

    @pytest.mark.asyncio
    async def test_unregister_tool(self, registry):
        """Test unregistering a tool"""
        tool = MockTool("removable")
        await registry.register("removable", tool, tags=["temp"])

        # Verify tool exists
        assert await registry.get("removable") is tool

        # Unregister
        result = await registry.unregister("removable")
        assert result is True

        # Verify tool is gone
        assert await registry.get("removable") is None

        # Unregistering again should return False
        result = await registry.unregister("removable")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_tools_no_pattern(self, registry):
        """Test listing all tools without pattern"""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")

        await registry.register("tool1", tool1)
        await registry.register("tool2", tool2)

        tools = await registry.list_tools()
        assert len(tools) == 2
        tool_names = {reg.name for reg in tools}
        assert tool_names == {"tool1", "tool2"}

    @pytest.mark.asyncio
    async def test_list_tools_with_pattern(self, registry):
        """Test listing tools with pattern matching"""
        weather_tool = MockTool("get_weather")
        api_tool = MockTool("api_call")
        multi_tool = MockTool("multi_tool")

        await registry.register("get_weather", weather_tool, tags=["weather"])
        await registry.register("api_call", api_tool, tags=["api"])
        await registry.register("multi_tool", multi_tool, tags=["weather", "api"])

        # Test exact name match
        exact = await registry.list_tools("get_weather")
        assert len(exact) == 1
        assert exact[0].name == "get_weather"

        # Test tag wildcard
        weather_tools = await registry.list_tools("weather:*")
        assert len(weather_tools) == 2
        weather_names = {reg.name for reg in weather_tools}
        assert weather_names == {"get_weather", "multi_tool"}

        # Test specific tag:name
        specific = await registry.list_tools("api:api_call")
        assert len(specific) == 1
        assert specific[0].name == "api_call"

        # Test wildcard
        all_tools = await registry.list_tools("*")
        assert len(all_tools) == 3

    @pytest.mark.asyncio
    async def test_select_tools(self, registry):
        """Test selecting tools with multiple patterns"""
        tool1 = MockTool("weather_tool")
        tool2 = MockTool("api_tool")
        tool3 = MockTool("specific_tool")

        await registry.register("weather_tool", tool1, tags=["weather"])
        await registry.register("api_tool", tool2, tags=["api"])
        await registry.register("specific_tool", tool3, tags=["util"])

        # Select with multiple patterns
        selected = await registry.select_tools(["weather:*", "specific_tool"])

        assert len(selected) == 2
        assert "weather_tool" in selected
        assert "specific_tool" in selected
        assert selected["weather_tool"] is tool1
        assert selected["specific_tool"] is tool3

    @pytest.mark.asyncio
    async def test_list_tags(self, registry):
        """Test listing available tags"""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        tool3 = MockTool("tool3")

        await registry.register("tool1", tool1, tags=["weather", "api"])
        await registry.register("tool2", tool2, tags=["weather"])
        await registry.register("tool3", tool3, tags=["util"])

        tags = await registry.list_tags()
        expected = {
            "weather": 2,  # tool1 and tool2
            "api": 1,  # tool1
            "util": 1,  # tool3
        }
        assert tags == expected

    @pytest.mark.asyncio
    async def test_get_tools_by_tag(self, registry):
        """Test getting tools by specific tag"""
        weather1 = MockTool("weather1")
        weather2 = MockTool("weather2")
        api_tool = MockTool("api_tool")

        await registry.register("weather1", weather1, tags=["weather"])
        await registry.register("weather2", weather2, tags=["weather", "advanced"])
        await registry.register("api_tool", api_tool, tags=["api"])

        weather_tools = await registry.get_tools_by_tag("weather")
        assert len(weather_tools) == 2
        weather_names = {reg.name for reg in weather_tools}
        assert weather_names == {"weather1", "weather2"}

        advanced_tools = await registry.get_tools_by_tag("advanced")
        assert len(advanced_tools) == 1
        assert advanced_tools[0].name == "weather2"

        nonexistent = await registry.get_tools_by_tag("nonexistent")
        assert len(nonexistent) == 0

    @pytest.mark.asyncio
    async def test_thread_safety(self, registry):
        """Test concurrent operations are thread-safe"""
        tools = [MockTool(f"tool_{i}") for i in range(10)]

        async def register_tool(i):
            await registry.register(f"tool_{i}", tools[i], tags=[f"tag_{i}"])

        # Register tools concurrently
        await asyncio.gather(*[register_tool(i) for i in range(10)])

        # Verify all tools were registered
        all_tools = await registry.list_tools()
        assert len(all_tools) == 10

        # Verify concurrent access works
        async def get_tool(i):
            return await registry.get(f"tool_{i}")

        results = await asyncio.gather(*[get_tool(i) for i in range(10)])
        for i, result in enumerate(results):
            assert result is tools[i]


class TestGlobalRegistry:
    """Test global registry functions"""

    @pytest.mark.asyncio
    async def test_get_tool_registry(self):
        """Test getting global registry instance"""
        # Reset global state
        import good_agent.tools.registry

        good_agent.tools.registry._global_registry = None

        registry1 = await get_tool_registry()
        registry2 = await get_tool_registry()

        # Should return same instance
        assert registry1 is registry2
        assert registry1._initialized is True

    def test_get_tool_registry_sync(self):
        """Test synchronous global registry access"""
        # Reset global state
        import good_agent.tools.registry

        good_agent.tools.registry._global_registry = None

        registry = get_tool_registry_sync()
        assert registry is not None


class TestRegisterToolDecorator:
    """Test the @register_tool decorator"""

    def test_register_tool_decorator_basic(self):
        """Test basic tool registration decorator"""
        # Reset global state
        import good_agent.tools.registry

        good_agent.tools.registry._global_registry = None

        @register_tool(tags=["test"], version="1.0.0", auto_register=False)
        def test_function(param: str) -> str:
            """Test function for decorator"""
            return f"Result: {param}"

        # Check metadata was added
        assert hasattr(test_function, "_tool_registry_metadata")
        metadata = test_function._tool_registry_metadata
        assert metadata["name"] == "test_function"
        assert metadata["tags"] == ["test"]
        assert metadata["version"] == "1.0.0"
        assert metadata["description"] == "Test function for decorator"

    def test_register_tool_decorator_custom_name(self):
        """Test decorator with custom tool name"""

        @register_tool(name="custom_name", auto_register=False)
        def some_function():
            pass

        metadata = some_function._tool_registry_metadata
        assert metadata["name"] == "custom_name"

    @patch("good_agent.tools.registry.get_tool_registry_sync")
    @patch("good_agent.tools.tools.Tool")  # Patch where Tool is imported in registry
    def test_register_tool_decorator_auto_register(
        self, mock_tool_class, mock_get_registry
    ):
        """Test decorator with auto registration"""
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        # Mock Tool instance
        mock_tool = MagicMock()
        mock_tool_class.return_value = mock_tool

        @register_tool(tags=["auto"], auto_register=True)
        def auto_registered_tool():
            """Auto registered"""
            pass

        # Verify Tool was created with the function
        mock_tool_class.assert_called_once_with(auto_registered_tool)
        # Verify registry methods were called
        mock_registry.register_sync.assert_called_once()


class TestPatternMatching:
    """Test advanced pattern matching scenarios"""

    @pytest_asyncio.fixture
    async def populated_registry(self):
        """Registry with various tools for pattern testing"""
        registry = ToolRegistry()
        await registry.initialize(load_entry_points=False)

        # Weather tools
        await registry.register(
            "get_weather", MockTool("get_weather"), tags=["weather", "api"]
        )
        await registry.register(
            "weather_forecast",
            MockTool("weather_forecast"),
            tags=["weather", "forecast"],
        )

        # API tools
        await registry.register("http_get", MockTool("http_get"), tags=["api", "http"])
        await registry.register(
            "rest_call", MockTool("rest_call"), tags=["api", "rest"]
        )

        # Utility tools
        await registry.register(
            "string_utils", MockTool("string_utils"), tags=["util", "string"]
        )
        await registry.register(
            "math_calc", MockTool("math_calc"), tags=["util", "math"]
        )

        # Multi-tagged tool
        await registry.register(
            "advanced_weather",
            MockTool("advanced_weather"),
            tags=["weather", "api", "advanced"],
        )

        return registry

    @pytest.mark.asyncio
    async def test_complex_pattern_matching(self, populated_registry):
        """Test complex pattern matching scenarios"""
        registry = populated_registry

        # Test multiple tag selection
        selected = await registry.select_tools(["weather:*", "api:*"])
        # Should get: get_weather, weather_forecast, http_get, rest_call, advanced_weather
        assert len(selected) >= 5
        assert "get_weather" in selected
        assert "advanced_weather" in selected

        # Test specific combinations
        weather_api = await registry.list_tools("weather:*")
        weather_names = {reg.name for reg in weather_api}
        expected_weather = {"get_weather", "weather_forecast", "advanced_weather"}
        assert weather_names == expected_weather

        # Test exact matches
        exact = await registry.list_tools("string_utils")
        assert len(exact) == 1
        assert exact[0].name == "string_utils"

    @pytest.mark.asyncio
    async def test_pattern_edge_cases(self, populated_registry):
        """Test edge cases in pattern matching"""
        registry = populated_registry

        # Empty pattern should match nothing (except None which matches all)
        empty_results = await registry.list_tools("")
        assert len(empty_results) == 0

        # Pattern with non-existent tag
        nonexistent = await registry.list_tools("nonexistent:*")
        assert len(nonexistent) == 0

        # Pattern with colon but no tag part
        malformed = await registry.list_tools(":tool_name")
        assert len(malformed) == 0

        # Wildcard should match everything
        all_tools = await registry.list_tools("*")
        assert len(all_tools) == 7  # All registered tools
