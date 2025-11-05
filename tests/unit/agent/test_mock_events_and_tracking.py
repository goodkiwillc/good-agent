import asyncio

import pytest
from good_agent import Agent, AgentEvents
from good_agent.mock import MockAgent, create_citation, mock_message


@pytest.mark.asyncio
async def test_mock_triggers_llm_events():
    """Test that mock LLM calls trigger the expected agent events."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    # Track events
    llm_call_fired = False
    llm_response_fired = False

    def on_llm_call(ctx):
        nonlocal llm_call_fired
        llm_call_fired = True

    def on_llm_response(ctx):
        nonlocal llm_response_fired
        llm_response_fired = True

    # Subscribe to LLM events
    agent.on(AgentEvents.LLM_COMPLETE_BEFORE)(on_llm_call)
    agent.on(AgentEvents.LLM_COMPLETE_AFTER)(on_llm_response)

    mock_response = mock_message("Test response", role="assistant")

    with MockAgent(agent, mock_response):
        agent.append("Test question", role="user")
        await agent.call()

        # Give events time to fire (they may be async)
        await asyncio.sleep(0.1)

    # Check that events were triggered
    assert llm_call_fired, "LLM_COMPLETE_BEFORE event should be triggered"
    assert llm_response_fired, "LLM_COMPLETE_AFTER event should be triggered"


@pytest.mark.asyncio
async def test_mock_tracks_api_requests():
    """Test that MockAgent tracks API requests like the real model."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    responses = [
        mock_message("First", role="assistant"),
        mock_message("Second", role="assistant"),
    ]

    with MockAgent(agent, *responses) as mock:
        # Initially no requests
        assert len(mock.api_requests) == 0
        assert len(mock.api_responses) == 0

        # First call
        agent.append("Question 1", role="user")
        await agent.call()

        # Should have one request/response
        assert len(mock.api_requests) == 1
        assert len(mock.api_responses) == 1

        # Check request structure
        request = mock.api_requests[0]
        assert "messages" in request
        assert isinstance(request["messages"], list)

        # Check response structure
        response = mock.api_responses[0]
        assert hasattr(response, "choices")
        assert hasattr(response, "usage")
        assert hasattr(response, "model")

        # Second call
        agent.append("Question 2", role="user")
        await agent.call()

        # Should have two requests/responses
        assert len(mock.api_requests) == 2
        assert len(mock.api_responses) == 2


@pytest.mark.asyncio
async def test_mock_response_has_expected_structure():
    """Test that mock responses have the same structure as real LLM responses."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    mock_response = mock_message(
        "Test content",
        role="assistant",
        citations=[create_citation("https://example.com")],
    )

    with MockAgent(agent, mock_response) as mock:
        agent.append("Test", role="user")
        await agent.call()

        # Get the mock LLM response
        api_response = mock.api_responses[0]

        # Check it has expected fields
        assert hasattr(api_response, "id")
        assert hasattr(api_response, "model")
        assert hasattr(api_response, "created")
        assert hasattr(api_response, "choices")
        assert hasattr(api_response, "usage")

        # Check choices structure
        assert len(api_response.choices) == 1
        choice = api_response.choices[0]
        assert hasattr(choice, "message")
        assert hasattr(choice.message, "content")

        # Check usage structure
        assert hasattr(api_response.usage, "prompt_tokens")
        assert hasattr(api_response.usage, "completion_tokens")
        assert hasattr(api_response.usage, "total_tokens")

        # Usage should have reasonable values
        assert api_response.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_preserves_model_api_tracking():
    """Test that the mock model's API tracking works like the real model."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    responses = [
        mock_message("Answer 1", role="assistant"),
        mock_message("Answer 2", role="assistant"),
    ]

    with MockAgent(agent, *responses) as mock:
        # The mock model should have API tracking attributes
        assert hasattr(agent.model, "_api_requests")
        assert hasattr(agent.model, "_api_responses")

        # Make calls
        agent.append("Q1", role="user")
        await agent.call()

        # Check model's internal tracking
        assert len(agent.model._api_requests) == 1
        assert len(agent.model._api_responses) == 1

        agent.append("Q2", role="user")
        await agent.call()

        # Check updated tracking
        assert len(agent.model._api_requests) == 2
        assert len(agent.model._api_responses) == 2

        # Verify these match what MockAgent exposes
        assert mock.api_requests == agent.model._api_requests
        assert mock.api_responses == agent.model._api_responses

    # After exiting, the original model is restored
    # (It won't have the mock's API tracking)
    assert agent.model.__class__.__name__ != "MockQueuedLanguageModel"


@pytest.mark.asyncio
async def test_mock_message_events():
    """Test that message append events are triggered with mocks."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    append_events = []

    def on_append(ctx):
        append_events.append(ctx.parameters)

    agent.on(AgentEvents.MESSAGE_APPEND_AFTER)(on_append)

    mock_response = mock_message("Response", role="assistant")

    with MockAgent(agent, mock_response):
        # Append user message
        agent.append("Question", role="user")

        # Give event time to fire
        await asyncio.sleep(0.1)

        # Should trigger MESSAGE_APPEND_AFTER for user message
        assert len(append_events) == 1
        assert append_events[0]["message"].role == "user"

        # Call agent (will append assistant message)
        response = await agent.call()

        # Verify response was added to messages
        assert response in agent.messages
        assert response.content.strip() == "Response"

        # Note: agent.call() doesn't trigger MESSAGE_APPEND_AFTER event for the response
        # it directly adds to self.messages. This is by design.


@pytest.mark.asyncio
async def test_mock_error_events():
    """Test that mock triggers error events when exhausted."""
    agent = Agent("You are a helpful assistant")
    await agent.ready()

    error_events = []

    def on_error(ctx):
        error_events.append(ctx.parameters)

    agent.on(AgentEvents.LLM_ERROR)(on_error)

    # Only one response queued
    mock_response = mock_message("Only response", role="assistant")

    with MockAgent(agent, mock_response):
        # First call succeeds
        agent.append("Q1", role="user")
        await agent.call()

        # Second call should fail and trigger error event
        agent.append("Q2", role="user")
        with pytest.raises(ValueError, match="No more mock responses"):
            await agent.call()

        # Give event time to fire
        await asyncio.sleep(0.1)

        # Should have triggered llm:error event
        assert len(error_events) == 1
        assert "error" in error_events[0]
        assert isinstance(error_events[0]["error"], ValueError)
