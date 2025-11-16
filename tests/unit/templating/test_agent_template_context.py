import pytest
from good_agent import Agent, UserMessage
from good_agent.content import TemplateContentPart, TextContentPart


@pytest.mark.asyncio
async def test_agent_available_in_template_context():
    """Test that agent instance is available as 'agent' variable in templates."""
    agent = Agent("Test system prompt", context={"custom_value": "test123"})
    await agent.ready()

    # Test accessing agent ID
    agent.append("Agent ID: {{ agent.id }}")
    msg = agent.messages[-1]
    rendered = msg.render()
    assert str(agent.id) in rendered

    # Test accessing agent properties
    agent.append("Message count: {{ agent.messages | length }}")
    rendered = agent.messages[-1].render()
    assert str(len(agent.messages)) in rendered

    # Test accessing agent context through agent variable
    agent.append("Value via agent: {{ agent.context.custom_value }}")
    rendered = agent.messages[-1].render()
    assert "test123" in rendered

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_agent_in_rendering_context_methods():
    """Test that get_rendering_context methods include agent."""
    agent = Agent("Test", context={"key": "value"})
    await agent.ready()

    # Test sync method
    context = agent.get_rendering_context()
    assert "agent" in context
    assert context["agent"] is agent
    assert context["key"] == "value"

    # Test async method
    context = await agent.get_rendering_context_async()
    assert "agent" in context
    assert context["agent"] is agent
    assert context["key"] == "value"

    # Test with additional context
    context = agent.get_rendering_context({"extra": "data"})
    assert context["agent"] is agent
    assert context["extra"] == "data"

    # Test that additional context can override agent if explicitly provided
    context = agent.get_rendering_context({"agent": "overridden"})
    assert context["agent"] == "overridden"

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_agent_in_template_content_part():
    """Test that TemplateContentPart can access agent in templates."""
    agent = Agent("Test")
    await agent.ready()

    # Create a message with TemplateContentPart
    msg = UserMessage(
        content_parts=[
            TextContentPart(text="Prefix: "),
            TemplateContentPart(
                template="Agent {{ agent.id }} has {{ agent.messages | length }} messages"
            ),
        ]
    )
    agent.append(msg)

    # Render should have access to agent
    rendered = msg.render()
    assert str(agent.id) in rendered
    assert "2 messages" in rendered  # System + this message

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_agent_available_in_tool_templates():
    """Test that agent is available when rendering Template parameters for tools."""
    from good_agent import Template, tool

    @tool
    def test_tool(query: str) -> str:
        return f"Searched for: {query}"

    agent = Agent("Test", tools=[test_tool])
    await agent.ready()

    # Invoke tool with Template that uses agent
    result = await agent.tool_calls.invoke(
        test_tool, query=Template("Search from agent {{ agent.id }}")
    )

    assert str(agent.id) in result.response
    assert "Search from agent" in result.response

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_agent_with_context_providers():
    """Test that agent is available alongside context providers."""
    agent = Agent("Test")
    await agent.ready()

    # Add a context provider
    @agent.template.context_provider("dynamic_value")
    def get_dynamic():
        return "dynamic123"

    # Template using both agent and context provider
    agent.append("Agent {{ agent.id }} with dynamic: {{ dynamic_value }}")
    rendered = agent.messages[-1].render()

    assert str(agent.id) in rendered
    assert "dynamic123" in rendered

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_agent_in_nested_template_context():
    """Test agent availability in nested template contexts."""
    agent = Agent("Test", context={"level": "agent"})
    await agent.ready()

    # Message with its own context
    msg = UserMessage(
        content_parts=[
            TemplateContentPart(
                template="Level: {{ level }}, Agent: {{ agent.id }}",
                context_snapshot={"level": "message"},  # Override at message level
            )
        ]
    )
    agent.append(msg)

    rendered = msg.render()
    assert "Level: message" in rendered  # Message context takes precedence
    assert str(agent.id) in rendered  # Agent still available

    await agent.events.async_close()
