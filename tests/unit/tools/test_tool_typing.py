import asyncio
from typing import Any, cast

import pytest
from good_agent import Tool, ToolResponse, tool
from good_agent.tools import BoundTool
from pydantic import BaseModel, Field

ToolLike = Tool[Any, Any] | BoundTool[Any, Any, Any]


def as_tool(tool_obj: ToolLike) -> Tool[Any, Any]:
    assert isinstance(tool_obj, Tool)
    return cast(Tool[Any, Any], tool_obj)


async def run_tool(tool_obj: ToolLike, *args: Any, **kwargs: Any) -> ToolResponse[Any]:
    callable_tool = as_tool(tool_obj)
    return await cast(Any, callable_tool)(*args, **kwargs)


class TestBasicToolDecorator:
    """Test basic @tool decorator functionality."""

    def test_sync_function_decoration(self):
        """Test that sync functions are properly wrapped."""

        @tool
        def add_numbers(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        add_numbers = as_tool(add_numbers)

        # Verify it's a Tool instance
        assert isinstance(add_numbers, Tool)
        assert add_numbers.name == "add_numbers"
        assert add_numbers.description == "Add two numbers."

    @pytest.mark.asyncio
    async def test_sync_function_execution(self):
        """Test that sync functions can be executed via Tool.__call__."""

        @tool
        def multiply(x: int, y: int) -> int:
            """Multiply two numbers."""
            return x * y

        multiply = as_tool(multiply)

        # Tool.__call__ is always async
        result = await run_tool(multiply, 3, 4)

        assert isinstance(result, ToolResponse)
        assert result.success is True
        assert result.response == 12
        assert result.tool_name == "multiply"
        assert result.error is None

    def test_async_function_decoration(self):
        """Test that async functions are properly wrapped."""

        @tool
        async def fetch_data(query: str) -> str:
            """Fetch data asynchronously."""
            await asyncio.sleep(0.001)
            return f"Data for: {query}"

        fetch_data = as_tool(fetch_data)

        assert isinstance(fetch_data, Tool)
        assert fetch_data.name == "fetch_data"

    @pytest.mark.asyncio
    async def test_async_function_execution(self):
        """Test that async functions can be executed."""

        @tool
        async def process(data: str) -> str:
            """Process data."""
            await asyncio.sleep(0.001)
            return f"Processed: {data}"

        process = as_tool(process)

        result = await run_tool(process, "test")

        assert isinstance(result, ToolResponse)
        assert result.success is True
        assert result.response == "Processed: test"


class TestToolWithParameters:
    """Test @tool() decorator with parameters."""

    def test_tool_with_custom_name(self):
        """Test tool with custom name parameter."""

        def add(a: int, b: int) -> int:
            return a + b

        custom_adder = as_tool(
            tool(name="custom_adder", description="Adds numbers together")(cast(Any, add))
        )

        assert custom_adder.name == "custom_adder"
        assert custom_adder.description == "Adds numbers together"

    @pytest.mark.asyncio
    async def test_tool_with_retry(self):
        """Test tool with retry parameter."""
        call_count = 0

        def flaky_function(should_fail: bool) -> str:
            """Function that may fail."""
            nonlocal call_count
            call_count += 1
            if should_fail and call_count < 2:
                raise ValueError("Temporary failure")
            return "Success"

        flaky_tool = as_tool(tool(retry=True)(cast(Any, flaky_function)))

        # Note: retry logic would need to be tested with proper mocking
        # This just verifies the tool accepts the parameter
        result = await run_tool(flaky_tool, False)
        assert result.response == "Success"

    def test_tool_with_hidden_params(self):
        """Test tool with hidden parameters."""

        def api_call(endpoint: str, api_key: str) -> str:
            """Make API call."""
            return f"Called {endpoint}"

        hidden_api_call = as_tool(tool(hide=["api_key"])(cast(Any, api_call)))

        # Check that api_key is not in the signature
        sig = hidden_api_call.signature
        params = sig["function"]["parameters"]["properties"]
        assert "endpoint" in params
        assert "api_key" not in params


class TestComplexTypes:
    """Test tools with complex type annotations."""

    @pytest.mark.asyncio
    async def test_pydantic_model_input_output(self):
        """Test tool with Pydantic model input and output."""

        class SearchRequest(BaseModel):
            query: str = Field(description="Search query")
            limit: int = Field(default=10, description="Max results")

        class SearchResult(BaseModel):
            total: int
            results: list[dict[str, Any]]
            query: str

        @tool
        async def search(request: SearchRequest) -> SearchResult:
            """Search with structured input/output."""
            return SearchResult(
                total=100,
                query=request.query,
                results=[{"id": i} for i in range(min(request.limit, 3))],
            )

        search = as_tool(search)

        req = SearchRequest(query="test", limit=2)
        result = await run_tool(search, req)

        assert isinstance(result, ToolResponse)
        assert isinstance(result.response, SearchResult)
        assert result.response.query == "test"
        assert result.response.total == 100
        assert len(result.response.results) == 2

    @pytest.mark.asyncio
    async def test_optional_types(self):
        """Test tool with Optional types."""

        @tool
        def process_optional(value: str | None = None) -> int | None:
            """Process optional value."""
            if value:
                return len(value)
            return None

        process_optional = as_tool(process_optional)

        # Test with value
        result1 = await run_tool(process_optional, "hello")
        assert result1.response == 5

        # Test without value
        result2 = await run_tool(process_optional)
        assert result2.response is None
        assert result2.success is True  # Still successful, just returns None

    @pytest.mark.asyncio
    async def test_union_types(self):
        """Test tool with Union types."""

        @tool
        async def process_union(data: str | int) -> str | int:
            """Process union types."""
            if isinstance(data, str):
                return len(data)
            return data * 2

        process_union = as_tool(process_union)

        # Test with string
        result1 = await run_tool(process_union, "test")
        assert result1.response == 4

        # Test with int
        result2 = await run_tool(process_union, 10)
        assert result2.response == 20

    @pytest.mark.asyncio
    async def test_dict_and_list_types(self):
        """Test tool with Dict and List types."""

        @tool
        def process_collections(items: list[str], mapping: dict[str, int]) -> dict[str, Any]:
            """Process collections."""
            return {
                "item_count": len(items),
                "total_value": sum(mapping.values()),
                "first_item": items[0] if items else None,
            }

        process_collections = as_tool(process_collections)

        result = await run_tool(
            process_collections, items=["a", "b", "c"], mapping={"x": 1, "y": 2, "z": 3}
        )

        assert result.response["item_count"] == 3
        assert result.response["total_value"] == 6
        assert result.response["first_item"] == "a"


class TestErrorHandling:
    """Test error handling in tools."""

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test that tools handle errors gracefully."""

        @tool
        async def may_fail(should_fail: bool) -> str:
            """Function that may fail."""
            if should_fail:
                raise ValueError("Intentional failure")
            return "Success"

        may_fail = as_tool(may_fail)

        # Success case
        result_ok = await run_tool(may_fail, False)
        assert result_ok.success is True
        assert result_ok.response == "Success"
        assert result_ok.error is None

        # Failure case
        result_err = await run_tool(may_fail, True)
        assert result_err.success is False
        assert result_err.response is None
        assert result_err.error is not None
        assert "Intentional failure" in result_err.error
        assert result_err.tool_name == "may_fail"

    @pytest.mark.asyncio
    async def test_none_return_vs_error(self):
        """Test distinction between returning None and erroring."""

        @tool
        def returns_none(return_none: bool) -> str | None:
            """Function that may return None."""
            if return_none:
                return None
            return "Not none"

        returns_none = as_tool(returns_none)

        # Returning None is not an error
        result = await run_tool(returns_none, True)
        assert result.success is True
        assert result.response is None
        assert result.error is None


class TestDirectToolInstantiation:
    """Test direct Tool class instantiation."""

    @pytest.mark.asyncio
    async def test_direct_tool_creation_sync(self):
        """Test creating a Tool directly with a sync function."""

        def my_func(x: int) -> str:
            return f"Result: {x}"

        tool_instance = Tool(fn=my_func, name="my_tool", description="My custom tool")

        assert isinstance(tool_instance, Tool)
        assert tool_instance.name == "my_tool"
        assert tool_instance.description == "My custom tool"

        result = await tool_instance(42)
        assert result.response == "Result: 42"

    @pytest.mark.asyncio
    async def test_direct_tool_creation_async(self):
        """Test creating a Tool directly with an async function."""

        async def async_func(msg: str) -> str:
            await asyncio.sleep(0.001)
            return f"Async: {msg}"

        tool_instance = Tool(fn=async_func, name="async_tool", description="Async tool")

        result = await tool_instance("test")
        assert result.response == "Async: test"


class TestToolSignatureAndModel:
    """Test tool signature and model generation."""

    def test_tool_signature_generation(self):
        """Test that tools generate correct OpenAI-compatible signatures."""

        @tool
        def signature_test(
            required_str: str,
            required_int: int,
            optional_str: str | None = None,
            default_int: int = 10,
        ) -> dict[str, Any]:
            """Test signature generation."""
            return {}

        signature_test = as_tool(signature_test)

        sig = signature_test.signature

        assert sig["type"] == "function"
        assert sig["function"]["name"] == "signature_test"
        assert sig["function"]["description"] == "Test signature generation."

        params = sig["function"]["parameters"]
        assert params["type"] == "object"
        assert "required_str" in params["properties"]
        assert "required_int" in params["properties"]
        assert "optional_str" in params["properties"]
        assert "default_int" in params["properties"]

        required = params.get("required", [])
        assert "required_str" in required
        assert "required_int" in required
        assert "optional_str" not in required
        assert "default_int" not in required

    def test_tool_model_generation(self):
        """Test that tools generate Pydantic models correctly."""

        @tool
        def model_test(name: str, age: int) -> str:
            """Test model generation."""
            return f"{name} is {age}"

        model_test = as_tool(model_test)

        model = model_test.model

        assert hasattr(model, "model_fields")
        fields = model.model_fields
        assert "name" in fields
        assert "age" in fields

        # Test model instantiation
        instance = model(name="Alice", age=30)
        assert instance.name == "Alice"  # type: ignore
        assert instance.age == 30  # type: ignore


class TestToolResponseTyping:
    """Test ToolResponse typing and behavior."""

    @pytest.mark.asyncio
    async def test_tool_response_fields(self):
        """Test that ToolResponse has all expected fields."""

        @tool
        def simple() -> str:
            return "test"

        simple = as_tool(simple)

        result = await run_tool(simple)

        assert hasattr(result, "tool_name")
        assert hasattr(result, "tool_call_id")
        assert hasattr(result, "response")
        assert hasattr(result, "parameters")
        assert hasattr(result, "success")
        assert hasattr(result, "error")

    @pytest.mark.asyncio
    async def test_tool_response_parameters(self):
        """Test that ToolResponse captures parameters."""

        @tool
        def with_params(a: int, b: str) -> str:
            return f"{a}-{b}"

        with_params = as_tool(with_params)

        # Parameters are captured from kwargs, not args
        result = await run_tool(with_params, a=42, b="test")

        assert result.parameters == {"a": 42, "b": "test"}
        assert result.response == "42-test"

        # When called with positional args, parameters dict is empty
        result2 = await run_tool(with_params, 42, "test")
        assert result2.parameters == {}
        assert result2.response == "42-test"

    def test_tool_results_property(self):
        """Test that Tool tracks results."""

        @tool
        def tracked() -> str:
            return "result"

        tracked = as_tool(tracked)

        assert len(tracked.results) == 0

        # Note: Would need async context to test execution
        # This just verifies the property exists
