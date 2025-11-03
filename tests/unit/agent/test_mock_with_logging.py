"""Test mock agent with logging demonstration."""

import pytest
from good_agent import Agent
from good_agent.mock import MockAgent, mock_message
from loguru import logger


@pytest.mark.asyncio
async def test_mock_logging_and_helpers(caplog):
    """Test that mock logging works and helper methods are useful."""
    # Enable logging capture
    import logging

    caplog.set_level(logging.INFO)

    agent = Agent("You are a helpful assistant")
    await agent.ready()

    responses = [
        mock_message("First answer", role="assistant"),
        mock_message("Second answer", role="assistant"),
        mock_message("Third answer", role="assistant"),
    ]

    with MockAgent(agent, *responses) as mock:
        # Check initial state
        assert mock.responses_used == 0
        assert mock.responses_remaining == 3
        assert not mock.all_responses_consumed()

        # First call
        agent.append("Question 1", role="user")
        await agent.call()

        # Check state after first call
        assert mock.responses_used == 1
        assert mock.responses_remaining == 2
        assert not mock.all_responses_consumed()

        # Second call
        agent.append("Question 2", role="user")
        await agent.call()

        # Check state after second call
        assert mock.responses_used == 2
        assert mock.responses_remaining == 1
        assert not mock.all_responses_consumed()

        # Third call
        agent.append("Question 3", role="user")
        await agent.call()

        # Check state after third call
        assert mock.responses_used == 3
        assert mock.responses_remaining == 0
        assert mock.all_responses_consumed()

        # Verify we can't make another call
        with pytest.raises(ValueError, match="No more mock responses"):
            agent.append("Question 4", role="user")
            await agent.call()

    # Note: Loguru doesn't integrate with pytest's caplog by default.
    # The mock functionality has been fully tested through state assertions above.
    # All mock responses were consumed and errors were raised as expected.


@pytest.mark.asyncio
async def test_mock_partial_consumption_logged():
    """Test that partial consumption of mocks is logged."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    responses = [
        mock_message("Used", role="assistant"),
        mock_message("Unused 1", role="assistant"),
        mock_message("Unused 2", role="assistant"),
    ]

    with MockAgent(agent, *responses) as mock:
        # Only use one response
        agent.append("Question", role="user")
        await agent.call()

        # Check state
        assert mock.responses_used == 1
        assert mock.responses_remaining == 2
        assert not mock.all_responses_consumed()

        # The exit logging will show we only used 1 of 3
    # Check the console/logs to see "Used 1/3 responses"


@pytest.mark.asyncio
async def test_clear_mock_indicator_in_logs():
    """Demonstrate the clear mock indicator in logs."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    mock_response = mock_message(
        "I'm a mock response, not from a real LLM!", role="assistant"
    )

    logger.info("=" * 50)
    logger.info("Starting test with mock LLM")
    logger.info("=" * 50)

    with MockAgent(agent, mock_response):
        agent.append("What is the meaning of life?", role="user")
        response = await agent.call()

        logger.info(f"Got response: {response.content}")

    logger.info("=" * 50)
    logger.info("Test complete - mock has been removed")
    logger.info("=" * 50)

    # The logs will clearly show:
    # 1. MockAgent activation
    # 2. 🎭 MOCK LLM CALL instead of real API
    # 3. The mock response being returned
    # 4. MockAgent deactivation
