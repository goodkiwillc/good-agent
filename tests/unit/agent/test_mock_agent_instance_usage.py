import pytest
from good_agent import Agent
from good_agent.mock import MockAgent, mock_message


@pytest.mark.asyncio
async def test_mock_agent_instance_introspection():
    """Test that we can introspect the MockAgent instance for debugging."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    responses = [
        mock_message("First", role="assistant"),
        mock_message("Second", role="assistant"),
        mock_message("Third", role="assistant"),
    ]

    with MockAgent(agent, *responses) as mock_agent:
        # We can access the mock_agent instance for introspection
        assert len(mock_agent.responses) == 3
        assert mock_agent._mock_model is not None
        assert mock_agent._original_model is not None

        # After first call
        agent.append("Q1", role="user")
        await agent.call()

        # We can check the mock model's state
        assert mock_agent._mock_model.response_index == 1

        # After second call
        agent.append("Q2", role="user")
        await agent.call()
        assert mock_agent._mock_model.response_index == 2

        # We can see how many responses are left
        remaining = len(mock_agent.responses) - mock_agent._mock_model.response_index
        assert remaining == 1


@pytest.mark.asyncio
async def test_mock_agent_execute_alternative_api():
    """Test the execute() method as an alternative API for getting mock messages."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    responses = [
        mock_message("First", role="assistant"),
        mock_message("Second", role="assistant"),
    ]

    mock_agent = MockAgent(agent, *responses)

    # execute() yields messages directly without going through agent.call()
    messages = []
    async for msg in mock_agent.execute():
        messages.append(msg)

    assert len(messages) == 2
    assert messages[0].content.strip() == "First"
    assert messages[1].content.strip() == "Second"

    # Note: This doesn't actually add messages to the agent's history
    assert len(agent.messages) == 1  # Just the system message


@pytest.mark.asyncio
async def test_mock_agent_direct_call():
    """Test the call() method on MockAgent (legacy API)."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    mock_response = mock_message("Direct call response", role="assistant")

    # Must enter context for mock to be active
    with MockAgent(agent, mock_response) as mock_agent:
        msg = await mock_agent.call()
        assert msg.content.strip() == "Direct call response"

        # Note: Now that mock_agent.call() delegates to agent.call(),
        # the message IS added to agent's history (which is more correct)
        assert len(agent.messages) == 2  # System message + assistant response


@pytest.mark.asyncio
async def test_accessing_mock_agent_for_verification():
    """Show how the MockAgent instance could be used for test verification."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    responses = [
        mock_message("Answer 1", role="assistant"),
        mock_message("Answer 2", role="assistant"),
    ]

    with MockAgent(agent, *responses) as mock_agent:
        # Initial state
        assert mock_agent._mock_model.response_index == 0

        # Make calls
        agent.append("Q1", role="user")
        await agent.call()
        agent.append("Q2", role="user")
        await agent.call()

        # Verify all responses were consumed
        assert mock_agent._mock_model.response_index == len(responses)

        # Could add a helper method to MockAgent for this
        # assert mock_agent.all_responses_consumed()

        # Try to call again - should fail
        with pytest.raises(ValueError, match="No more mock responses"):
            agent.append("Q3", role="user")
            await agent.call()
