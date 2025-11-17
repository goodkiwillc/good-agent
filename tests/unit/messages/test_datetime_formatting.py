from datetime import date, datetime, timedelta

import pytest
from good_agent import Agent


@pytest.mark.asyncio
async def test_datetime_strftime_formatting():
    """Test that datetime objects can be formatted with strftime."""
    agent = Agent("Test")
    await agent.initialize()

    # Test various strftime formats
    agent.append("Full date: {{ today.strftime('%B %d, %Y') }}")
    rendered = agent.messages[-1].render()

    # Should contain month name and year
    import calendar

    month_names = calendar.month_name[1:]  # Skip empty first element
    assert any(month in rendered for month in month_names)
    assert str(date.today().year) in rendered

    # Test time formatting
    agent.append("Time: {{ now.strftime('%H:%M:%S') }}")
    rendered = agent.messages[-1].render()
    assert ":" in rendered  # Contains time separator

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_datetime_attribute_access():
    """Test that datetime attributes can be accessed in templates."""
    agent = Agent("Test")
    await agent.initialize()

    agent.append(
        "Year: {{ today.year }}, Month: {{ today.month }}, Day: {{ today.day }}"
    )
    rendered = agent.messages[-1].render()

    today = date.today()
    assert str(today.year) in rendered
    assert str(today.month) in rendered
    assert str(today.day) in rendered

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_datetime_methods():
    """Test that datetime methods can be called in templates."""
    agent = Agent("Test")
    await agent.initialize()

    # Test date() method
    agent.append("Date only: {{ today.date() }}")
    rendered = agent.messages[-1].render()
    assert str(date.today()) in rendered

    # Test isoformat() method
    agent.append("ISO: {{ now.isoformat() }}")
    rendered = agent.messages[-1].render()
    assert "T" in rendered  # ISO format includes T separator

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_datetime_with_timedelta():
    """Test date arithmetic with timedelta in context."""
    # Add timedelta to context for date arithmetic
    agent = Agent("Test", context={"timedelta": timedelta})
    await agent.initialize()

    # Test date arithmetic
    agent.append("Tomorrow: {{ (today + timedelta(days=1)).strftime('%Y-%m-%d') }}")
    rendered = agent.messages[-1].render()

    tomorrow = date.today() + timedelta(days=1)
    assert tomorrow.strftime("%Y-%m-%d") in rendered

    # Test subtraction
    agent.append("Yesterday: {{ (today - timedelta(days=1)).strftime('%Y-%m-%d') }}")
    rendered = agent.messages[-1].render()

    yesterday = date.today() - timedelta(days=1)
    assert yesterday.strftime("%Y-%m-%d") in rendered

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_datetime_in_complex_templates():
    """Test datetime in complex template scenarios."""
    agent = Agent("Test", context={"project": "MyProject"})
    await agent.initialize()

    # Complex template with multiple datetime uses
    agent.append("""
Report for {{ project }}
Generated on: {{ today.strftime('%A, %B %d, %Y') }}
Time: {{ now.strftime('%I:%M %p %Z') }}
ISO Date: {{ today.isoformat() }}
Week: {{ today.strftime('%U') }}
""")
    rendered = agent.messages[-1].render()

    assert "MyProject" in rendered
    assert str(date.today().year) in rendered
    # Should contain day name (Monday, Tuesday, etc.)
    import calendar

    day_names = list(calendar.day_name)
    assert any(day in rendered for day in day_names)

    await agent.events.async_close()


@pytest.mark.asyncio
async def test_datetime_comparison():
    """Test that datetime objects maintain their type for comparisons."""
    from good_agent.components.template_manager import _GLOBAL_CONTEXT_PROVIDERS

    today_val = _GLOBAL_CONTEXT_PROVIDERS["today"]()
    now_val = _GLOBAL_CONTEXT_PROVIDERS["now"]()

    # Both should be datetime objects
    assert isinstance(today_val, datetime)
    assert isinstance(now_val, datetime)

    # today should be less than or equal to now (since today is at midnight)
    assert today_val <= now_val

    # today should have zero time components
    assert today_val.hour == 0
    assert today_val.minute == 0
    assert today_val.second == 0
    assert today_val.microsecond == 0

    # Both should have timezone info
    assert today_val.tzinfo is not None
    assert now_val.tzinfo is not None
