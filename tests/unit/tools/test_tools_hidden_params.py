from typing import Any, cast

import pytest
from good_agent import Agent
from good_agent.tools import Tool, ToolResponse, tool, wrap_callable_as_tool


class TestHiddenParameters:
    """Test hidden parameter functionality"""

    def test_tool_with_hidden_params(self):
        """Test that Tool class properly hides parameters"""

        def my_func(query: str, api_key: str, verbose: bool = False) -> str:
            """Test function with hidden params"""
            return f"Query: {query}, Key: {api_key}, Verbose: {verbose}"

        # Create tool with hidden parameters
        tool_instance = wrap_callable_as_tool(my_func, hide=["api_key", "verbose"])

        # Check that hidden params are stored
        assert tool_instance._hidden_params == {"api_key", "verbose"}

        # Check that hidden params are not in metadata
        assert "query" in tool_instance._tool_metadata.parameters
        assert "api_key" not in tool_instance._tool_metadata.parameters
        assert "verbose" not in tool_instance._tool_metadata.parameters

        # Check that signature excludes hidden params
        signature = tool_instance.signature
        properties = signature["function"]["parameters"]["properties"]
        assert "query" in properties
        assert "api_key" not in properties
        assert "verbose" not in properties

    def test_tool_decorator_with_hide(self):
        """Test @tool decorator with hide parameter"""

        def my_tool(input: str, secret: str) -> str:
            """Tool with hidden secret"""
            return f"{input}-{secret}"

        tool_decorator: Any = tool
        decorated_tool = cast(Tool[Any, Any], tool_decorator(hide=["secret"])(my_tool))

        # Check that hidden params are stored
        assert decorated_tool._hidden_params == {"secret"}

        # Check metadata
        assert "input" in decorated_tool._tool_metadata.parameters
        assert "secret" not in decorated_tool._tool_metadata.parameters

        # Check signature
        signature = decorated_tool.signature
        properties = signature["function"]["parameters"]["properties"]
        assert "input" in properties
        assert "secret" not in properties

    def test_wrap_callable_with_hide(self):
        """Test wrap_callable_as_tool with hide parameter"""

        def my_func(a: int, b: int, api_key: str) -> int:
            """Add two numbers"""
            return a + b

        tool_instance = wrap_callable_as_tool(my_func, hide=["api_key"])

        # Check that hidden params work
        assert tool_instance._hidden_params == {"api_key"}
        assert "a" in tool_instance._tool_metadata.parameters
        assert "b" in tool_instance._tool_metadata.parameters
        assert "api_key" not in tool_instance._tool_metadata.parameters

    @pytest.mark.asyncio
    async def test_invoke_with_hidden_params(self):
        """Test that invoke only records visible parameters"""

        async def search_tool_impl(query: str, api_key: str) -> str:
            """Search with hidden API key"""
            return f"Results for {query} using key {api_key}"

        search_tool = wrap_callable_as_tool(search_tool_impl, hide=["api_key"])

        agent = Agent("Test agent")
        await agent.initialize()  # Ensure agent is ready

        # Invoke tool with both visible and hidden parameters
        response: ToolResponse[Any] = await agent.invoke(
            search_tool, query="test query", api_key="secret123"
        )

        # Check response
        assert response.success
        assert "Results for test query using key secret123" in str(response.response)

        # Check that only visible params are recorded in tool call
        assistant_msg = agent.assistant[-1]
        tool_calls = assistant_msg.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1

        tool_call = tool_calls[0]
        import orjson

        recorded_params = orjson.loads(tool_call.function.arguments)

        # Only visible params should be in the recorded call
        assert recorded_params == {"query": "test query"}
        assert "api_key" not in recorded_params

    @pytest.mark.asyncio
    async def test_invoke_callable_with_hide(self):
        """Test invoking a regular callable with hide parameter"""

        async def process_data(data: str, token: str, debug: bool = False) -> str:
            """Process data with token"""
            return f"Processed {data} with token {token}, debug={debug}"

        agent = Agent("Test agent")
        await agent.initialize()  # Ensure agent is ready

        # Invoke callable with hide parameter
        response: ToolResponse[Any] = await agent.invoke(
            process_data,
            hide=["token", "debug"],
            data="test_data",
            token="auth_token",
            debug=True,
        )

        # Check response
        assert response.success
        assert "Processed test_data with token auth_token, debug=True" in str(response.response)

        # Check recorded parameters
        assistant_msg = agent.assistant[-1]
        tool_calls = assistant_msg.tool_calls
        assert tool_calls is not None
        tool_call = tool_calls[0]
        import orjson

        recorded_params = orjson.loads(tool_call.function.arguments)

        # Only visible params should be recorded
        assert recorded_params == {"data": "test_data"}
        assert "token" not in recorded_params
        assert "debug" not in recorded_params

    def test_record_invocation_with_visible_params_only(self):
        """Test tool_calls.record_invocation records only visible parameters"""

        agent = Agent("Test agent")
        # Note: This is a sync test, agent will initialize synchronously

        # Create a tool response
        response = ToolResponse(
            tool_name="search",
            response="Search results",
            parameters={
                "query": "test",
                "api_key": "secret",
            },  # Both params in response
            success=True,
        )

        # Add tool invocation, specifying only visible params
        agent.add_tool_invocation(
            tool="search",
            response=response,
            parameters={"query": "test"},  # Only visible param
        )

        # Check that assistant message has only visible params
        assistant_msg = None
        for msg in agent.messages:
            if msg.role == "assistant" and hasattr(msg, "tool_calls") and msg.tool_calls:
                assistant_msg = msg
                break

        assert assistant_msg is not None
        tool_calls = assistant_msg.tool_calls
        assert tool_calls is not None
        tool_call = tool_calls[0]
        import orjson

        recorded_params = orjson.loads(tool_call.function.arguments)

        # Only visible param should be recorded
        assert recorded_params == {"query": "test"}
        assert "api_key" not in recorded_params

    @pytest.mark.asyncio
    async def test_invoke_func_with_hide(self):
        """Test invoke_func with hide parameter"""

        async def api_call(endpoint: str, api_key: str, timeout: int = 30) -> str:
            """Make API call"""
            return f"Called {endpoint} with key {api_key}, timeout={timeout}"

        agent = Agent("Test agent")
        await agent.initialize()  # Ensure agent is ready

        # Create bound function with hidden params
        bound_call = agent.invoke_func(
            api_call,
            hide=["api_key", "timeout"],
            api_key="secret_key",  # Bind hidden param
            timeout=60,  # Bind another hidden param
        )

        # Call bound function with visible param
        response: ToolResponse[Any] = await bound_call(endpoint="/users")

        # Check response
        assert response.success
        assert "Called /users with key secret_key, timeout=60" in str(response.response)

        # Check recorded parameters
        assistant_msg = agent.assistant[-1]
        tool_calls = assistant_msg.tool_calls
        assert tool_calls is not None
        tool_call = tool_calls[0]
        import orjson

        recorded_params = orjson.loads(tool_call.function.arguments)

        # Only visible param should be recorded
        assert recorded_params == {"endpoint": "/users"}
        assert "api_key" not in recorded_params
        assert "timeout" not in recorded_params

    def test_tool_model_excludes_hidden_params(self):
        """Test that Tool.model property excludes hidden parameters"""

        def func_with_params(visible: str, hidden: str, optional: int = 5) -> str:
            """Function with mixed params"""
            return f"{visible}-{hidden}-{optional}"

        tool_instance = wrap_callable_as_tool(func_with_params, hide=["hidden"])

        # Get the generated model
        model = tool_instance.model

        # Check model fields
        fields = model.model_fields
        assert "visible" in fields
        assert "optional" in fields
        assert "hidden" not in fields

        # Verify model can be instantiated with only visible params
        instance = model(visible="test", optional=10)
        data = instance.model_dump()
        assert data["visible"] == "test"
        assert data["optional"] == 10

    @pytest.mark.asyncio
    async def test_hidden_params_still_work_in_execution(self):
        """Test that hidden parameters are still passed during execution"""

        async def multiply_impl(value: int, multiplier: int) -> int:
            """Multiply value by hidden multiplier"""
            return value * multiplier

        multiply = wrap_callable_as_tool(multiply_impl, hide=["multiplier"])

        agent = Agent("Test agent")
        await agent.initialize()  # Ensure agent is ready

        # Invoke with both params
        response: ToolResponse[Any] = await agent.invoke(
            multiply,
            value=5,
            multiplier=3,  # Hidden but still functional
        )

        # Check that function executed correctly with hidden param
        assert response.success
        assert response.response == 15  # 5 * 3

        # But hidden param not in recorded call
        assistant_msg = agent.assistant[-1]
        tool_calls = assistant_msg.tool_calls
        assert tool_calls is not None
        tool_call = tool_calls[0]
        import orjson

        recorded_params = orjson.loads(tool_call.function.arguments)
        assert recorded_params == {"value": 5}
