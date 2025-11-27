from datetime import date, datetime

import pytest
from good_agent import Agent
from good_agent.extensions.template_manager import _GLOBAL_CONTEXT_PROVIDERS, Template


@pytest.mark.asyncio
async def test_today_context_provider():
    """Test that 'today' context provider returns datetime object at midnight."""
    agent = Agent("Test")
    await agent.initialize()

    # Test in template - should render as datetime string
    agent.append("Date: {{ today }}")
    rendered = agent.messages[-1].render()

    # Should contain today's date as provided by the context provider
    today_val = _GLOBAL_CONTEXT_PROVIDERS["today"]()
    assert str(today_val.date()) in rendered

    # Test direct provider call - should return datetime object
    today_value = _GLOBAL_CONTEXT_PROVIDERS["today"]()
    assert isinstance(today_value, datetime)
    # Should be at midnight
    assert today_value.hour == 0
    assert today_value.minute == 0
    assert today_value.second == 0
    assert today_value.microsecond == 0
    # Should be today's date (or previous day if timezone is behind)
    # Note: date.today() uses local time, while provider might use UTC or PT
    # We just ensure it's close enough (within 24h)
    provider_date = today_value.date()
    system_date = date.today()
    delta = abs((provider_date - system_date).days)
    assert delta <= 1, (
        f"Provider date {provider_date} too far from system date {system_date}"
    )

    await agent.events.close()


@pytest.mark.asyncio
async def test_now_context_provider():
    """Test that 'now' context provider returns datetime object."""
    agent = Agent("Test")
    await agent.initialize()

    # Test in template
    agent.append("Time: {{ now }}")
    rendered = agent.messages[-1].render()

    # Should contain a datetime string
    assert ":" in rendered  # Time component present

    # Test direct provider call - should return datetime object
    now_value = _GLOBAL_CONTEXT_PROVIDERS["now"]()
    assert isinstance(now_value, datetime)
    # Should have timezone info (UTC)
    assert now_value.tzinfo is not None

    await agent.events.close()


@pytest.mark.asyncio
async def test_context_providers_in_tool_templates():
    """Test that default context providers work in tool templates."""
    from good_agent import tool

    @tool
    def test_tool(message: str) -> str:
        return f"Processed: {message}"

    agent = Agent("Test", tools=[test_tool])
    await agent.initialize()

    # Use context providers in Template parameter with formatting
    result = await agent.invoke(
        test_tool,
        message=Template(
            "Event on {{ today.strftime('%Y-%m-%d') }} at {{ now.strftime('%H:%M') }}"
        ),
    )

    # Should contain today's date in YYYY-MM-DD format
    today_val = _GLOBAL_CONTEXT_PROVIDERS["today"]()
    assert str(today_val.date()) in result.response
    # Should contain time in HH:MM format
    assert ":" in result.response

    await agent.events.close()


@pytest.mark.asyncio
async def test_context_providers_with_agent_context():
    """Test that default providers work alongside agent context."""
    agent = Agent("Test", context={"custom": "value"})
    await agent.initialize()

    # Use both default providers and agent context
    agent.append("Date: {{ today }}, Custom: {{ custom }}, Agent: {{ agent.id }}")
    rendered = agent.messages[-1].render()

    # All should be present
    today_val = _GLOBAL_CONTEXT_PROVIDERS["today"]()
    assert str(today_val.date()) in rendered
    assert "value" in rendered
    assert str(agent.id) in rendered

    await agent.events.close()


@pytest.mark.asyncio
async def test_context_providers_priority():
    """Test that context can override default providers if needed."""
    agent = Agent("Test")
    await agent.initialize()

    # Override 'today' with custom value
    agent.context._chainmap.maps[0]["today"] = "2024-01-01"

    agent.append("Date: {{ today }}")
    rendered = agent.messages[-1].render()

    # Should use the override, not the provider
    assert "2024-01-01" in rendered
    # Use the provider to check what "today" would have been
    today_val = _GLOBAL_CONTEXT_PROVIDERS["today"]()
    # Only assert if the provider's date is different from the override
    if str(today_val.date()) != "2024-01-01":
        assert str(today_val.date()) not in rendered

    await agent.events.close()


def test_global_providers_registered():
    """Test that default providers are registered globally."""
    assert "today" in _GLOBAL_CONTEXT_PROVIDERS
    assert "now" in _GLOBAL_CONTEXT_PROVIDERS

    # Test they're callable
    assert callable(_GLOBAL_CONTEXT_PROVIDERS["today"])
    assert callable(_GLOBAL_CONTEXT_PROVIDERS["now"])

    # Test they return datetime objects
    today_val = _GLOBAL_CONTEXT_PROVIDERS["today"]()
    now_val = _GLOBAL_CONTEXT_PROVIDERS["now"]()

    assert isinstance(today_val, datetime)
    assert isinstance(now_val, datetime)

    # Test properties
    assert today_val.hour == 0  # today is at midnight
    assert today_val.minute == 0
    assert today_val.tzinfo is not None  # Has timezone
    assert now_val.tzinfo is not None  # Has timezone
