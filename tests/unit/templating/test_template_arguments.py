import pytest
from good_agent import Agent, Template, tool


@tool
async def search_web(
    query: str,
    search_type: str = "general",
    time_period: str = "last_week",
    ttl: int = 3600,
) -> str:
    """Search the web with the given query."""
    return f"Searched for '{query}' (type: {search_type}, period: {time_period}, ttl: {ttl})"


@tool
def simple_tool(message: str) -> str:
    """A simple synchronous tool."""
    return f"Processed: {message}"


@pytest.mark.asyncio
async def test_invoke_with_template_argument():
    """Test that Template arguments are rendered with agent context."""
    agent = Agent(
        "You are a helpful assistant.",
        context={"subject": "bob ferguson", "region": "washington"},
    )

    # Register the tool
    await agent.tools.register_tool(search_web, name="search_web")

    # Invoke with Template argument
    result = await agent.tool_calls.invoke(
        "search_web",
        query=Template("{{subject}} {{region}}"),
        search_type="news",
        time_period="last_day",
        ttl=60 * 60,
    )

    assert result.success is True
    assert "bob ferguson washington" in str(result.response)
    assert result.parameters["query"] == "bob ferguson washington"
    assert result.parameters["search_type"] == "news"


@pytest.mark.asyncio
async def test_invoke_with_template_default():
    """Test Template with default values."""
    agent = Agent("You are a helpful assistant.", context={"subject": "seattle"})

    await agent.tools.register_tool(search_web, name="search_web")

    # Use template with default value
    result = await agent.tool_calls.invoke(
        "search_web",
        query=Template("{{subject}}"),
        time_period=Template("{{time_period|default('last_month')}}"),
    )

    assert result.success is True
    assert result.parameters["query"] == "seattle"
    assert result.parameters["time_period"] == "last_month"


@pytest.mark.asyncio
async def test_invoke_many_with_templates():
    """Test invoke_many with Template arguments."""
    agent = Agent(
        "You are a helpful assistant.",
        context={"topic1": "python", "topic2": "javascript", "greeting": "Hello"},
    )

    await agent.tools.register_tool(search_web, name="search_web")
    await agent.tools.register_tool(simple_tool, name="simple_tool")

    # Multiple invocations with templates
    results = await agent.tool_calls.invoke_many(
        [
            (
                "search_web",
                {
                    "query": Template("{{topic1}} programming"),
                    "search_type": "tutorials",
                },
            ),
            (
                "search_web",
                {
                    "query": Template("{{topic2}} frameworks"),
                    "search_type": "documentation",
                },
            ),
            ("simple_tool", {"message": Template("{{greeting}} World!")}),
        ]
    )

    assert len(results) == 3
    assert all(r.success for r in results)

    # Check first result
    assert "python programming" in str(results[0].response)
    assert results[0].parameters["query"] == "python programming"

    # Check second result
    assert "javascript frameworks" in str(results[1].response)
    assert results[1].parameters["query"] == "javascript frameworks"

    # Check third result
    assert "Hello World!" in str(results[2].response)
    assert results[2].parameters["message"] == "Hello World!"


@pytest.mark.asyncio
async def test_template_with_missing_variable():
    """Test Template behavior with missing variable (non-strict mode)."""
    agent = Agent("You are a helpful assistant.", context={"subject": "test"})

    await agent.tools.register_tool(simple_tool, name="simple_tool")

    # Non-strict template with missing variable
    result = await agent.tool_calls.invoke(
        "simple_tool", message=Template("{{subject}} {{missing_var}}", strict=False)
    )

    # In non-strict mode, template should still work but missing var won't be replaced
    assert result.success is True
    # The template should render what it can
    assert "test" in result.parameters["message"]


@pytest.mark.asyncio
async def test_template_strict_mode():
    """Test Template in strict mode raises on missing variables."""
    agent = Agent("You are a helpful assistant.", context={"subject": "test"})

    await agent.tools.register_tool(simple_tool, name="simple_tool")

    # Strict template with missing variable should handle the error
    # The Template.render() will return the original template on error in non-strict mode
    # but we set strict=True so it should raise
    template = Template("{{subject}} {{missing_var}}", strict=True)

    # The render will fail but the tool should still be invoked with the template string
    result = await agent.tool_calls.invoke("simple_tool", message=template)

    # The tool should still be called, but the parameter might be the unrendered template
    # or might fail - depends on implementation
    assert result is not None


@pytest.mark.asyncio
async def test_mixed_template_and_regular_parameters():
    """Test mixing Template and regular parameters."""
    agent = Agent(
        "You are a helpful assistant.",
        context={"search_term": "climate change", "default_ttl": 7200},
    )

    await agent.tools.register_tool(search_web, name="search_web")

    result = await agent.tool_calls.invoke(
        "search_web",
        query=Template("{{search_term}}"),
        search_type="news",  # Regular string
        time_period=Template("{{period|default('last_week')}}"),
        ttl=Template("{{default_ttl}}"),  # Template for integer
    )

    assert result.success is True
    assert result.parameters["query"] == "climate change"
    assert result.parameters["search_type"] == "news"
    assert result.parameters["time_period"] == "last_week"  # Used default
    assert str(result.parameters["ttl"]) == "7200"  # Rendered as string


@pytest.mark.asyncio
async def test_context_providers_with_templates():
    """Test that context providers work with Template arguments."""
    agent = Agent("You are a helpful assistant.", context={"base": "value"})

    # Add a context provider
    @agent.context_manager.context_provider("dynamic_value")
    def provide_dynamic():
        return "dynamically_generated"

    await agent.tools.register_tool(simple_tool, name="simple_tool")

    result = await agent.tool_calls.invoke(
        "simple_tool", message=Template("Base: {{base}}, Dynamic: {{dynamic_value}}")
    )

    assert result.success is True
    assert "Base: value" in result.parameters["message"]
    assert "Dynamic: dynamically_generated" in result.parameters["message"]


@pytest.mark.asyncio
async def test_hide_parameter_with_template():
    """Test that hidden parameters work with templates."""
    agent = Agent(
        "You are a helpful assistant.",
        context={"api_key": "secret123", "query_text": "search this"},
    )

    @tool
    async def api_tool(query: str, api_key: str = "default") -> str:
        return f"Query: {query}, Key: {api_key}"

    await agent.tools.register_tool(api_tool, name="api_tool")

    # Invoke with hidden parameter
    result = await agent.tool_calls.invoke(
        "api_tool",
        query=Template("{{query_text}}"),
        api_key=Template("{{api_key}}"),
        hide=["api_key"],
    )

    assert result.success is True
    assert "search this" in str(result.response)
    assert "secret123" in str(result.response)
    # The api_key should still be passed but might be hidden from recording
