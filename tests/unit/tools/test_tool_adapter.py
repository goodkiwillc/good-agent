import copy
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from good_agent import Agent, AgentComponent, ToolMessage, tool
from good_agent.core.components import (
    AdapterMetadata,
    ConflictStrategy,
    ToolAdapter,
    ToolAdapterRegistry,
)
from good_agent.tools import BoundTool, Tool, ToolResponse

ToolLike = Tool[Any, Any] | BoundTool[Any, Any, Any]


def as_tool(tool_obj: ToolLike) -> Tool[Any, Any]:
    assert isinstance(tool_obj, Tool)
    return cast(Tool[Any, Any], tool_obj)


async def run_tool(tool_obj: ToolLike, *args: Any, **kwargs: Any) -> ToolResponse[Any]:
    callable_tool = as_tool(tool_obj)
    return await cast(Any, callable_tool)(*args, **kwargs)


# Test tools
@tool
async def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch content from a URL."""
    return f"Content from {url}"


fetch_url = as_tool(fetch_url)


@tool
async def process_data(input_url: str, output_url: str) -> dict:
    """Process data from input URL to output URL."""
    return {"input": input_url, "output": output_url}


process_data = as_tool(process_data)


class SimpleAdapter(ToolAdapter):
    """Simple test adapter that adds a prefix parameter."""

    def __init__(self, component, prefix="test"):
        super().__init__(component, priority=100)
        self.prefix = prefix
        self.adapt_count = 0
        self.param_count = 0

    def should_adapt(self, tool, agent):
        return "url" in tool.name.lower()

    def analyze_transformation(self, tool, signature):
        return AdapterMetadata(modified_params=set(), added_params={"prefix"}, removed_params=set())

    def adapt_signature(self, tool, signature, agent):
        self.adapt_count += 1
        adapted = copy.deepcopy(signature)
        params = adapted["function"]["parameters"]["properties"]
        params["prefix"] = {
            "type": "string",
            "description": "Prefix for the URL",
            "default": self.prefix,
        }
        return adapted

    def adapt_parameters(self, tool_name, parameters, agent):
        self.param_count += 1
        adapted = dict(parameters)
        # Remove the prefix parameter before passing to tool
        prefix = adapted.pop("prefix", self.prefix)
        # Add prefix to URL if present
        if "url" in adapted:
            adapted["url"] = f"{prefix}:{adapted['url']}"
        return adapted


class ConflictingAdapter(ToolAdapter):
    """Adapter that conflicts with SimpleAdapter by modifying same param."""

    def should_adapt(self, tool, agent):
        return "url" in tool.name.lower()

    def analyze_transformation(self, tool, signature):
        # This conflicts by also adding "prefix"
        return AdapterMetadata(
            modified_params=set(),
            added_params={"prefix", "suffix"},
            removed_params=set(),
        )

    def adapt_signature(self, tool, signature, agent):
        adapted = copy.deepcopy(signature)
        params = adapted["function"]["parameters"]["properties"]
        params["prefix"] = {"type": "string", "description": "URL prefix"}
        params["suffix"] = {"type": "string", "description": "URL suffix"}
        return adapted

    def adapt_parameters(self, tool_name, parameters, agent):
        return parameters


class URLToIndexAdapter(ToolAdapter):
    """Adapter that changes URL type from string to integer."""

    def __init__(self, component):
        super().__init__(component, priority=150)  # Higher priority
        self.urls = ["http://example.com", "http://test.com"]

    def should_adapt(self, tool, agent):
        return tool.name == "fetch_url"

    def analyze_transformation(self, tool, signature):
        return AdapterMetadata(
            modified_params=set(), added_params={"url_idx"}, removed_params={"url"}
        )

    def adapt_signature(self, tool, signature, agent):
        adapted = copy.deepcopy(signature)
        params = adapted["function"]["parameters"]["properties"]
        if "url" in params:
            del params["url"]
            params["url_idx"] = {
                "type": "integer",
                "description": "URL index (0-based)",
                "minimum": 0,
            }
            # Update required list
            if "url" in adapted["function"]["parameters"].get("required", []):
                required = adapted["function"]["parameters"]["required"]
                required[required.index("url")] = "url_idx"
        return adapted

    def adapt_parameters(self, tool_name, parameters, agent):
        adapted = dict(parameters)
        if "url_idx" in adapted:
            idx = adapted.pop("url_idx")
            if 0 <= idx < len(self.urls):
                adapted["url"] = self.urls[idx]
        return adapted


class ResponseAdapter(ToolAdapter):
    """Adapter that transforms tool responses."""

    def __init__(self, component):
        super().__init__(component, priority=120)
        self.adapt_response_calls = 0

    def should_adapt(self, tool, agent):
        return tool.name == "fetch_url"

    def analyze_transformation(self, tool, signature):
        return AdapterMetadata(modified_params=set(), added_params=set(), removed_params=set())

    def adapt_signature(self, tool, signature, agent):
        return copy.deepcopy(signature)

    def adapt_parameters(self, tool_name, parameters, agent):
        return parameters

    def adapt_response(self, tool_name, response, agent):
        self.adapt_response_calls += 1
        return ToolResponse(
            tool_name=response.tool_name,
            tool_call_id=response.tool_call_id,
            response=f"adapted:{response.response}",
            parameters=response.parameters,
            success=response.success,
            error=response.error,
        )


class NoResponseAdapter(ResponseAdapter):
    """Adapter that leaves responses unchanged."""

    def adapt_response(self, tool_name, response, agent):
        self.adapt_response_calls += 1
        return None


class TestToolMessageHelpers:
    def test_with_tool_response_creates_new_message(self):
        original_response = ToolResponse(
            tool_name="fetch_url",
            tool_call_id="call-1",
            response="original",
            parameters={"url": "example.com"},
            success=True,
            error=None,
        )
        message = ToolMessage(
            "original",
            tool_call_id="call-1",
            tool_name="fetch_url",
            tool_response=original_response,
        )

        new_response = ToolResponse(
            tool_name="fetch_url",
            tool_call_id="call-1",
            response="updated",
            parameters={"url": "example.com"},
            success=True,
            error=None,
        )

        new_message = message.with_tool_response(new_response)

        assert new_message is not message
        assert new_message.tool_response == new_response
        assert new_message.model_dump(exclude={"tool_response"}) == message.model_dump(
            exclude={"tool_response"}
        )
        assert message.tool_response == original_response


class TestToolAdapter:
    """Test basic ToolAdapter functionality."""

    def test_adapter_initialization(self):
        """Test adapter can be initialized with component."""
        component = MagicMock()
        adapter = SimpleAdapter(component)

        assert adapter.component == component
        assert adapter.priority == 100
        assert adapter.conflict_strategy == ConflictStrategy.CHAIN

    def test_adapter_with_custom_priority(self):
        """Test adapter priority setting."""
        component = MagicMock()
        adapter = URLToIndexAdapter(component)

        assert adapter.priority == 150  # Higher priority

    def test_should_adapt(self):
        """Test adapter's should_adapt logic."""
        component = MagicMock()
        adapter = SimpleAdapter(component)
        agent = MagicMock()

        assert adapter.should_adapt(fetch_url, agent) is True

        # Create a tool without "url" in name
        @tool
        async def other_tool():
            pass

        other_tool = as_tool(other_tool)

        assert adapter.should_adapt(other_tool, agent) is False

    def test_signature_adaptation(self):
        """Test signature transformation."""
        component = MagicMock()
        adapter = SimpleAdapter(component)
        agent = MagicMock()

        original_sig = fetch_url.signature
        adapted_sig = adapter.adapt_signature(fetch_url, original_sig, agent)

        # Check that prefix was added
        params = adapted_sig["function"]["parameters"]["properties"]
        assert "prefix" in params
        assert params["prefix"]["type"] == "string"

        # Check original params still present
        assert "url" in params
        assert "timeout" in params

        # Check adapt_count incremented
        assert adapter.adapt_count == 1

    def test_parameter_adaptation(self):
        """Test parameter transformation."""
        component = MagicMock()
        adapter = SimpleAdapter(component, prefix="https")
        agent = MagicMock()

        params = {"url": "example.com", "prefix": "http"}
        adapted = adapter.adapt_parameters("fetch_url", params, agent)

        # Check prefix was applied and removed
        assert "prefix" not in adapted
        assert adapted["url"] == "http:example.com"

        # Check param_count incremented
        assert adapter.param_count == 1

    def test_type_transformation(self):
        """Test adapter that changes parameter types."""
        component = MagicMock()
        adapter = URLToIndexAdapter(component)
        agent = MagicMock()

        original_sig = fetch_url.signature
        adapted_sig = adapter.adapt_signature(fetch_url, original_sig, agent)

        # Check URL was replaced with index
        params = adapted_sig["function"]["parameters"]["properties"]
        assert "url" not in params
        assert "url_idx" in params
        assert params["url_idx"]["type"] == "integer"

        # Test parameter reverse transformation
        params = {"url_idx": 0, "timeout": 10}
        adapted = adapter.adapt_parameters("fetch_url", params, agent)

        assert "url_idx" not in adapted
        assert adapted["url"] == "http://example.com"


class TestToolAdapterRegistry:
    """Test ToolAdapterRegistry functionality."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = ToolAdapterRegistry()

        assert registry._adapters == []
        assert registry._default_strategy == ConflictStrategy.CHAIN

    def test_adapter_registration(self):
        """Test registering adapters."""
        registry = ToolAdapterRegistry()
        component = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = URLToIndexAdapter(component)

        registry.register(adapter1)
        registry.register(adapter2)

        assert len(registry._adapters) == 2
        # Check priority sorting (higher priority first)
        assert registry._adapters[0] == adapter2  # priority 150
        assert registry._adapters[1] == adapter1  # priority 100

    def test_duplicate_registration(self):
        """Test that duplicate registration is ignored."""
        registry = ToolAdapterRegistry()
        component = MagicMock()
        adapter = SimpleAdapter(component)

        registry.register(adapter)
        registry.register(adapter)  # Duplicate

        assert len(registry._adapters) == 1

    def test_adapter_unregistration(self):
        """Test unregistering adapters."""
        registry = ToolAdapterRegistry()
        component = MagicMock()
        adapter = SimpleAdapter(component)

        registry.register(adapter)
        assert len(registry._adapters) == 1

        registry.unregister(adapter)
        assert len(registry._adapters) == 0

    def test_get_adapters_for_tool(self):
        """Test finding applicable adapters for a tool."""
        registry = ToolAdapterRegistry()
        component = MagicMock()
        agent = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = URLToIndexAdapter(component)

        registry.register(adapter1)
        registry.register(adapter2)

        # Both adapters should apply to fetch_url
        adapters = registry.get_adapters_for_tool(fetch_url, agent)
        assert len(adapters) == 2

        # Check caching
        adapters2 = registry.get_adapters_for_tool(fetch_url, agent)
        assert adapters == adapters2

    def test_conflict_detection(self):
        """Test detecting conflicts between adapters."""
        registry = ToolAdapterRegistry()
        component = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = ConflictingAdapter(component)

        conflicts = registry.detect_conflicts(fetch_url, [adapter1, adapter2])

        # Both add "prefix" parameter - conflict!
        assert len(conflicts) == 1
        param, adapters = conflicts[0]
        assert param == "prefix"
        assert set(adapters) == {adapter1, adapter2}

    def test_no_conflicts(self):
        """Test when adapters don't conflict."""
        registry = ToolAdapterRegistry()
        component = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = URLToIndexAdapter(component)

        # These don't conflict - one adds prefix, other replaces url
        conflicts = registry.detect_conflicts(fetch_url, [adapter1, adapter2])

        assert len(conflicts) == 0

    def test_exclusive_strategy_with_conflicts(self):
        """Test EXCLUSIVE strategy raises on conflicts."""
        registry = ToolAdapterRegistry(default_strategy=ConflictStrategy.EXCLUSIVE)
        component = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = ConflictingAdapter(component)

        conflicts = [("prefix", [adapter1, adapter2])]

        with pytest.raises(ValueError) as exc_info:
            registry.resolve_conflicts(conflicts)

        assert "Multiple adapters attempting" in str(exc_info.value)
        assert "prefix" in str(exc_info.value)

    def test_chain_strategy(self):
        """Test CHAIN strategy allows conflicts."""
        registry = ToolAdapterRegistry(default_strategy=ConflictStrategy.CHAIN)
        component = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = ConflictingAdapter(component)

        conflicts = [("prefix", [adapter1, adapter2])]

        # Should not raise
        registry.resolve_conflicts(conflicts)

    def test_adapt_signature_with_conflicts(self):
        """Test full signature adaptation with conflict checking."""
        registry = ToolAdapterRegistry()
        component = MagicMock()
        agent = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = URLToIndexAdapter(component)

        registry.register(adapter1)
        registry.register(adapter2)

        original_sig = fetch_url.signature
        adapted_sig = registry.adapt_signature(fetch_url, original_sig, agent)

        params = adapted_sig["function"]["parameters"]["properties"]

        # URLToIndexAdapter (higher priority) runs first
        # - Removes "url", adds "url_idx"
        # SimpleAdapter runs second
        # - Adds "prefix"

        assert "url" not in params  # Removed by URLToIndexAdapter
        assert "url_idx" in params  # Added by URLToIndexAdapter
        assert "prefix" in params  # Added by SimpleAdapter

    def test_adapt_parameters_reverse_order(self):
        """Test parameters are adapted in reverse order."""
        registry = ToolAdapterRegistry()
        component = MagicMock()
        agent = MagicMock()

        adapter1 = SimpleAdapter(component)
        adapter2 = URLToIndexAdapter(component)

        registry.register(adapter1)
        registry.register(adapter2)

        # First, adapt the signature to track which adapters applied
        original_sig = fetch_url.signature
        registry.adapt_signature(fetch_url, original_sig, agent)

        # Now adapt parameters (should apply in reverse)
        params = {"url_idx": 0, "prefix": "test", "timeout": 10}
        adapted = registry.adapt_parameters("fetch_url", params, agent)

        # In reverse order:
        # 1. SimpleAdapter runs first
        #    - Removes "prefix" parameter
        #    - Would add prefix to "url" if it existed, but it doesn't yet
        # 2. URLToIndexAdapter runs second
        #    - Converts "url_idx" to "url"

        assert "url_idx" not in adapted
        assert "prefix" not in adapted
        assert "url" in adapted
        # URL won't have prefix because SimpleAdapter ran before URL existed
        assert adapted["url"] == "http://example.com"


@pytest.mark.asyncio
class TestAgentComponentIntegration:
    """Test integration with AgentComponent."""

    async def test_component_with_adapter(self):
        """Test component registering and using adapters."""

        class TestComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.adapter = SimpleAdapter(self)

            async def install(self, agent):
                await super().install(agent)
                self.register_tool_adapter(self.adapter)

        component = TestComponent()
        agent = Agent("Test agent", tools=[fetch_url], extensions=[component])
        await agent.initialize()

        # Verify adapter was registered
        assert len(component._tool_adapter_registry._adapters) == 1
        assert component.adapter in component._tool_adapter_registry._adapters

    async def test_adapter_handlers_setup(self):
        """Test that adapter event handlers are set up."""

        class TestComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.adapter = SimpleAdapter(self)

        component = TestComponent()
        agent = Agent("Test agent", tools=[fetch_url], extensions=[component])
        await agent.initialize()

        # Register adapter after installation
        component.register_tool_adapter(component.adapter)

        # Check that adapter was registered
        assert len(component._tool_adapter_registry._adapters) == 1
        assert component.adapter in component._tool_adapter_registry._adapters

        # Check that component has the event handler methods (set up via decorators)
        assert hasattr(component, "_on_tools_generate_signature_adapter")
        assert hasattr(component, "_on_tool_call_before_adapter")

    async def test_adapter_disable_with_component(self):
        """Test adapters respect component enabled state."""

        class TestComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.adapter = SimpleAdapter(self)

            async def install(self, agent):
                await super().install(agent)
                self.register_tool_adapter(self.adapter)

        component = TestComponent()
        agent = Agent("Test agent", tools=[fetch_url], extensions=[component])
        await agent.initialize()

        # Disable component
        component.enabled = False

        # Adapter should not be applied when component is disabled
        # (This is handled by the event handlers checking enabled state)
        assert component.enabled is False


@pytest.mark.asyncio
class TestToolAdapterResponseTransformation:
    async def test_tool_response_transformation_on_message_append(self):
        class ResponseComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.adapter = ResponseAdapter(self)

            async def install(self, agent):
                await super().install(agent)
                self.register_tool_adapter(self.adapter)

        component = ResponseComponent()
        agent = Agent("Test agent", tools=[fetch_url], extensions=[component])
        await agent.initialize()

        component._tool_adapter_registry.adapt_signature(fetch_url, fetch_url.signature, agent)

        tool_response = ToolResponse(
            tool_name="fetch_url",
            tool_call_id="call-123",
            response="original",
            parameters={"url": "http://example.com"},
            success=True,
            error=None,
        )

        message = ToolMessage(
            "original",
            tool_call_id="call-123",
            tool_name="fetch_url",
            tool_response=tool_response,
        )

        appended = await agent.append_async(message)

        assert appended is not message
        assert appended.tool_response.response == "adapted:original"
        assert appended.tool_response.tool_name == "fetch_url"
        assert appended.content_parts == message.content_parts
        assert component.adapter.adapt_response_calls == 1

    async def test_non_tool_messages_pass_through(self):
        class ResponseComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.adapter = ResponseAdapter(self)

            async def install(self, agent):
                await super().install(agent)
                self.register_tool_adapter(self.adapter)

        component = ResponseComponent()
        agent = Agent("Test agent", tools=[fetch_url], extensions=[component])
        await agent.initialize()

        message = await agent.append_async(agent.model.create_message(content="hi", role="user"))

        assert message.role == "user"
        assert component.adapter.adapt_response_calls == 0

    async def test_adapter_without_response_transformation(self):
        class NoResponseComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.adapter = NoResponseAdapter(self)

            async def install(self, agent):
                await super().install(agent)
                self.register_tool_adapter(self.adapter)

        component = NoResponseComponent()
        agent = Agent("Test agent", tools=[fetch_url], extensions=[component])
        await agent.initialize()

        component._tool_adapter_registry.adapt_signature(fetch_url, fetch_url.signature, agent)

        tool_response = ToolResponse(
            tool_name="fetch_url",
            tool_call_id="call-456",
            response="original",
            parameters={"url": "http://example.com"},
            success=True,
            error=None,
        )

        message = ToolMessage(
            "original",
            tool_call_id="call-456",
            tool_name="fetch_url",
            tool_response=tool_response,
        )

        appended = await agent.append_async(message)

        assert appended is message
        assert appended.tool_response == tool_response
        assert component.adapter.adapt_response_calls == 1


@pytest.mark.asyncio
async def test_end_to_end_adapter_flow():
    """Test complete flow from LLM to tool execution."""

    class IndexComponent(AgentComponent):
        def __init__(self):
            super().__init__()
            self.adapter = URLToIndexAdapter(self)

        async def install(self, agent):
            await super().install(agent)
            self.register_tool_adapter(self.adapter)

    component = IndexComponent()
    agent = Agent("Test agent", tools=[fetch_url], extensions=[component])
    await agent.initialize()

    # What the LLM sees: fetch_url(url_idx: int, timeout: int)
    # LLM calls with: {"url_idx": 0, "timeout": 5}
    # Adapter transforms to: {"url": "http://example.com", "timeout": 5}
    # Tool executes with real URL

    # Simulate the transformation
    params_from_llm = {"url_idx": 0, "timeout": 5}
    adapted = component.adapter.adapt_parameters("fetch_url", params_from_llm, agent)

    assert adapted == {"url": "http://example.com", "timeout": 5}

    # Tool would execute successfully with adapted parameters
    result = await run_tool(fetch_url, **adapted)
    assert result.response == "Content from http://example.com"
    assert result.success is True
