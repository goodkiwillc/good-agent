import asyncio
from datetime import datetime

import pytest
from good_agent import Agent, UserMessage
from good_agent.content import TemplateContentPart
from good_agent.messages import RenderMode
from good_agent.templating import Template


def test_context_priority_ordering():
    """Test that context sources have correct priority."""
    import asyncio

    async def run_test():
        # Config context (lowest priority)
        config_context = {"var": "config", "config_only": "config_value"}

        # Agent context (middle priority)
        agent_context = {"var": "agent", "agent_only": "agent_value"}

        # Create agent with both config and agent context
        agent = Agent("Test system", context={**config_context, **agent_context})
        await agent.ready()

        # Message context (highest priority)
        message_context = {"var": "message", "message_only": "message_value"}

        # Add message with template and local context
        msg = UserMessage(
            content="Values: {{ var }}, {{ config_only }}, {{ agent_only }}, {{ message_only }}",
            context=message_context,
        )
        agent.append(msg)

        # Render the message
        rendered = agent.messages[-1].render()

        # Verify priority: message > agent > config
        assert "message" in rendered  # message context wins for 'var'
        assert "config_value" in rendered  # config_only still accessible
        assert "agent_value" in rendered  # agent_only still accessible
        assert "message_value" in rendered  # message_only from message context

        await agent.async_close()

    asyncio.run(run_test())


@pytest.mark.asyncio
async def test_context_providers_in_messages():
    """Test that messages can access context providers."""
    agent = Agent("Test system")
    await agent.ready()

    # Register a context provider
    @agent.template.context_provider("timestamp")
    def get_timestamp():
        return datetime.now().isoformat()

    @agent.template.context_provider("user_name")
    def get_user_name():
        return "TestUser"

    # Add message with template using context providers
    agent.append("Time: {{ timestamp }}, User: {{ user_name }}")

    # Render the message
    rendered = agent.messages[-1].render()

    # Verify context providers were resolved
    assert "TestUser" in rendered
    # Timestamp should be an ISO format datetime
    assert "T" in rendered  # ISO format contains 'T' between date and time

    await agent.async_close()


@pytest.mark.asyncio
async def test_tool_parameter_templates():
    """Test that tool parameters resolve templates correctly."""
    from good_agent import tool
    from good_agent.tools import ToolResponse

    # Define a tool
    @tool
    async def fetch(url: str, key: str) -> str:
        return f"Fetched from {url} with key {key}"

    agent = Agent(
        "Test system",
        context={"base_url": "http://api.example.com", "api_key": "secret123"},
        tools=[fetch],  # Pass tools at creation time
    )
    await agent.ready()

    # Manually execute tool with template parameters
    # First resolve the templates
    params = {
        "url": Template("{{ base_url }}/endpoint"),
        "key": Template("{{ api_key }}"),
    }

    # Use agent's internal method to render template parameters
    rendered_params = await agent._render_template_parameters(params)

    # Verify the parameters were resolved correctly
    assert rendered_params["url"] == "http://api.example.com/endpoint"
    assert rendered_params["key"] == "secret123"

    # Now simulate tool invocation with rendered parameters
    response = ToolResponse(
        response=f"Fetched from {rendered_params['url']} with key {rendered_params['key']}",
        parameters=rendered_params,
        tool_name="fetch",
        tool_call_id="test_call",
        success=True,
    )

    # Add the tool invocation to history
    agent.add_tool_invocation("fetch", response, rendered_params)

    # Verify the tool message was added
    tool_msg = agent.messages[-1]
    assert tool_msg.role == "tool"
    assert "http://api.example.com/endpoint" in tool_msg.render()
    assert "secret123" in tool_msg.render()

    await agent.async_close()


@pytest.mark.asyncio
async def test_backward_compatibility():
    """Test that old patterns still work."""
    agent = Agent("Test system", context={"global": "value"})
    await agent.ready()

    # Old pattern: direct message creation with content
    msg = UserMessage(content="Template: {{ global }}")
    agent.append(msg)

    rendered = agent.messages[-1].render()
    assert "value" in rendered

    # Old pattern: using render() without mode
    rendered_default = agent.messages[-1].render()
    assert rendered_default == rendered

    await agent.async_close()


@pytest.mark.asyncio
async def test_context_provider_override():
    """Test that message context can override context providers."""
    agent = Agent("Test system")
    await agent.ready()

    # Register a context provider
    @agent.template.context_provider("value")
    def get_value():
        return "provider_value"

    # Add message without override - should use provider
    agent.append("Value: {{ value }}")
    rendered1 = agent.messages[-1].render()
    assert "provider_value" in rendered1

    # Add message with override - should use message context
    msg = UserMessage(content="Value: {{ value }}", context={"value": "override_value"})
    agent.append(msg)
    rendered2 = agent.messages[-1].render()
    assert "override_value" in rendered2
    assert "provider_value" not in rendered2

    await agent.async_close()


@pytest.mark.asyncio
async def test_template_content_part_with_snapshot():
    """Test that TemplateContentPart context_snapshot works correctly."""
    agent = Agent("Test system", context={"global": "global_value"})
    await agent.ready()

    # Create a TemplateContentPart with a context snapshot
    part = TemplateContentPart(
        template="Global: {{ global }}, Snapshot: {{ snapshot }}",
        context_snapshot={"snapshot": "snapshot_value", "global": "overridden"},
    )

    # Add message with the content part
    msg = UserMessage(content_parts=[part])
    agent.append(msg)

    # Render the message
    rendered = agent.messages[-1].render()

    # Snapshot should override global context
    assert "snapshot_value" in rendered  # Check snapshot value
    assert "overridden" in rendered  # Check override works
    assert "global_value" not in rendered  # Original value should not appear

    await agent.async_close()


@pytest.mark.asyncio
async def test_render_mode_in_context():
    """Test that render_mode is available in template context."""
    agent = Agent("Test system")
    await agent.ready()

    # Add template that uses render_mode
    agent.append("Mode: {{ render_mode }}")

    # Test different render modes
    rendered_display = agent.messages[-1].render()  # Default is DISPLAY
    assert "display" in rendered_display

    rendered_llm = agent.messages[-1].render(mode=RenderMode.LLM)
    assert "llm" in rendered_llm

    rendered_storage = agent.messages[-1].render(mode=RenderMode.STORAGE)
    assert "storage" in rendered_storage

    await agent.async_close()


@pytest.mark.asyncio
async def test_empty_agent_context():
    """Test that templates work with no agent context."""
    agent = Agent("Test system")  # No context provided
    await agent.ready()

    # Add template that doesn't require context
    agent.append("Static text and {{ 'literal' }}")

    rendered = agent.messages[-1].render()
    assert "Static text and literal" in rendered

    await agent.async_close()


@pytest.mark.asyncio
async def test_get_rendering_context_method():
    """Test the new get_rendering_context method directly."""
    agent = Agent("Test system", context={"base": "base_value", "override": "base"})
    await agent.ready()

    # Register a context provider
    @agent.template.context_provider("provider")
    def get_provider():
        return "provider_value"

    # Test without additional context
    context1 = agent.get_rendering_context()
    assert context1["base"] == "base_value"
    assert context1["override"] == "base"
    assert context1["provider"] == "provider_value"

    # Test with additional context (should have highest priority)
    additional = {"override": "additional", "new": "new_value"}
    context2 = agent.get_rendering_context(additional)
    assert context2["base"] == "base_value"
    assert context2["override"] == "additional"  # Additional wins
    assert context2["new"] == "new_value"
    assert context2["provider"] == "provider_value"

    await agent.async_close()


@pytest.mark.asyncio
async def test_async_context_provider():
    """Test that async context providers work correctly."""
    agent = Agent("Test system")
    await agent.ready()

    # Register an async context provider
    @agent.template.context_provider("async_value")
    async def get_async_value():
        # Simulate async operation
        await asyncio.sleep(0.001)
        return "async_result"

    # Use get_rendering_context_async
    context = await agent.get_rendering_context_async()
    assert context["async_value"] == "async_result"

    await agent.async_close()


@pytest.mark.asyncio
async def test_agentless_message_rendering():
    """Test that messages without an agent can still render templates."""
    # Create message without agent
    msg = UserMessage(content="Static {{ 'text' }}")

    # Should still be able to render with basic Jinja2
    rendered = msg.render()
    assert "Static text" in rendered

    # Test with context
    msg_with_context = UserMessage(content="Value: {{ key }}", context={"key": "value"})
    rendered_with_context = msg_with_context.render()
    assert "Value: value" in rendered_with_context


@pytest.mark.asyncio
async def test_template_error_handling():
    """Test that template errors are handled gracefully."""
    agent = Agent("Test system")
    await agent.ready()

    # Add template with undefined variable (without strict mode)
    agent.append("Undefined: {{ undefined_var }}")

    # Should render with empty string for undefined
    rendered = agent.messages[-1].render()
    assert "Undefined:" in rendered

    # Add template with syntax error
    part = TemplateContentPart(template="Bad syntax: {{ unclosed")
    msg = UserMessage(content_parts=[part])
    agent.append(msg)

    # Should raise an exception on render with bad syntax
    import pytest

    with pytest.raises(RuntimeError) as exc_info:
        agent.messages[-1].render()

    # Check the error message contains helpful information
    assert "Error rendering template" in str(exc_info.value)

    await agent.async_close()


@pytest.mark.asyncio
async def test_system_prompt_with_template_variable():
    """Test that system prompts with template variables are properly detected and rendered."""
    from datetime import datetime

    # Create agent with system prompt containing template variable
    system_prompt = "You are an assistant. Today is {{today.strftime('%A, %B %d, %Y')}}"

    # Create context with today's date
    today = datetime.now()
    agent = Agent(system_prompt, context={"today": today})
    await agent.ready()

    # Check that the system message exists
    assert len(agent.messages) > 0
    assert agent.messages[0].role == "system"

    # Check that the system message has a TemplateContentPart, not TextContentPart
    system_msg = agent.messages[0]
    assert len(system_msg.content_parts) > 0

    # The content part should be a TemplateContentPart since it contains {{ }}
    from good_agent.content import TemplateContentPart

    content_part = system_msg.content_parts[0]
    assert isinstance(content_part, TemplateContentPart), (
        f"Expected TemplateContentPart but got {type(content_part).__name__}"
    )

    # Render the system message
    rendered = system_msg.render()

    # Check that the date was properly rendered
    expected_date = today.strftime("%A, %B %d, %Y")
    assert expected_date in rendered, (
        f"Expected '{expected_date}' in rendered output, but got: {rendered}"
    )

    # Also verify it doesn't contain the raw template syntax
    assert "{{today" not in rendered
    assert "}}" not in rendered

    await agent.async_close()


@pytest.mark.asyncio
async def test_system_prompt_template_with_citation_manager():
    """Test that CitationManager doesn't interfere with template detection in system prompts."""
    from datetime import datetime

    from good_agent.content import TemplateContentPart
    from good_agent.extensions import CitationManager

    # Create agent WITH CitationManager extension
    system_prompt = "You are an assistant. Today is {{today.strftime('%A, %B %d, %Y')}}"

    # Create context with today's date
    today = datetime.now()

    # Create CitationManager and agent with it as extension
    citation_manager = CitationManager()
    agent = Agent(
        system_prompt, context={"today": today}, extensions=[citation_manager]
    )
    await agent.ready()

    # Check that the system message exists
    assert len(agent.messages) > 0
    assert agent.messages[0].role == "system"

    # Check that the system message has a TemplateContentPart, not TextContentPart
    system_msg = agent.messages[0]
    assert len(system_msg.content_parts) > 0

    # The content part should STILL be a TemplateContentPart despite CitationManager
    content_part = system_msg.content_parts[0]
    assert isinstance(content_part, TemplateContentPart), (
        f"CitationManager broke template detection! Expected TemplateContentPart but got {type(content_part).__name__}"
    )

    # Render the system message
    rendered = system_msg.render()

    # Check that the date was properly rendered
    expected_date = today.strftime("%A, %B %d, %Y")
    assert expected_date in rendered, (
        f"Expected '{expected_date}' in rendered output, but got: {rendered}"
    )

    # Also verify it doesn't contain the raw template syntax
    assert "{{today" not in rendered
    assert "}}" not in rendered

    await agent.async_close()
