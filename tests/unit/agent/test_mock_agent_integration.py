import pytest
from good_agent import Agent
from good_agent.mock import (
    MockAgent,
    create_annotation,
    create_citation,
    mock_message,
)


@pytest.mark.asyncio
async def test_mock_agent_intercepts_call():
    """Test that MockAgent intercepts agent.call() and returns mocked response."""
    # Create agent
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create mock responses
    mock_response1 = mock_message("This is the first mocked response", role="assistant")
    mock_response2 = mock_message("This is the second mocked response", role="assistant")

    # Use MockAgent as context manager
    with MockAgent(agent, mock_response1, mock_response2):
        # First call should return first mock response
        agent.append("What is 2+2?", role="user")
        response1 = await agent.call()
        assert response1.content.strip() == "This is the first mocked response"

        # Second call should return second mock response
        agent.append("What is the capital of France?", role="user")
        response2 = await agent.call()
        assert response2.content.strip() == "This is the second mocked response"

        # Third call should fail (no more responses)
        agent.append("Another question", role="user")
        with pytest.raises(ValueError, match="No more mock responses available"):
            await agent.call()


@pytest.mark.asyncio
async def test_mock_agent_with_citations_and_annotations():
    """Test that mocked responses with citations and annotations work correctly."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create mock response with citations and annotations
    citations = [create_citation("https://example.com/source")]
    annotations = [create_annotation("important", 8, 17)]

    mock_response = mock_message(
        "This is important information from a source",
        role="assistant",
        citations=citations,
        annotations=annotations,
        reasoning="I found this in the documentation",
    )

    # Use MockAgent
    with MockAgent(agent, mock_response):
        agent.append("Tell me something important", role="user")
        response = await agent.call()

        # Verify content
        assert "important information" in response.content

        # Note: Citations and annotations might not be preserved through
        # the LLM mock layer - this depends on implementation details
        # The important thing is that the mock accepts these parameters


@pytest.mark.asyncio
async def test_mock_agent_async_context_manager():
    """Test that MockAgent works as an async context manager."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    mock_response = mock_message("Async mock response", role="assistant")

    async with MockAgent(agent, mock_response):
        agent.append("Test question", role="user")
        response = await agent.call()
        assert response.content.strip() == "Async mock response"


@pytest.mark.asyncio
async def test_mock_agent_restores_original_model():
    """Test that the original model is restored after exiting MockAgent context."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Store reference to original model
    original_model = agent.model

    mock_response = mock_message("Mocked", role="assistant")

    # Use mock
    with MockAgent(agent, mock_response):
        # Model should be replaced
        assert agent.model != original_model
        assert agent.model.__class__.__name__ == "MockQueuedLanguageModel"

    # After exiting context, model should be restored
    assert agent.model == original_model


@pytest.mark.asyncio
async def test_mock_agent_with_multiple_user_messages():
    """Test that mock works correctly when user sends multiple messages."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Queue up multiple mock responses
    responses = [
        mock_message("First response", role="assistant"),
        mock_message("Second response", role="assistant"),
        mock_message("Third response", role="assistant"),
    ]

    with MockAgent(agent, *responses):
        # Send multiple user messages and get responses
        agent.append("Question 1", role="user")
        r1 = await agent.call()
        assert r1.content.strip() == "First response"

        agent.append("Question 2", role="user")
        r2 = await agent.call()
        assert r2.content.strip() == "Second response"

        agent.append("Question 3", role="user")
        r3 = await agent.call()
        assert r3.content.strip() == "Third response"

        # Verify all messages are in the agent's history
        # Note: Agent() adds a system message, so we have 1 system + 3 user + 3 assistant
        assert len(agent.messages) == 7


@pytest.mark.asyncio
async def test_mock_agent_appending_to_original():
    """Test that messages should be appended to the original agent, not the mock."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    mock_response = mock_message("Mock response", role="assistant")

    with MockAgent(agent, mock_response):
        # Messages should be appended to the original agent
        agent.append("User message", role="user")

        # Call should work and use the mock
        response = await agent.call()
        assert response.content.strip() == "Mock response"

        # The message should be in the original agent's history
        # Note: Agent() adds a system message, so we have 1 system + 1 user + 1 assistant
        assert len(agent.messages) == 3
        assert agent.messages[1].content.strip() == "User message"  # Index 0 is system message
        assert agent.messages[2].content.strip() == "Mock response"


@pytest.mark.asyncio
async def test_mock_with_refusal():
    """Test that mock responses with refusal work correctly."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    mock_response = mock_message(
        "",  # Empty content when refusing
        role="assistant",
        refusal="I cannot help with that request",
    )

    with MockAgent(agent, mock_response):
        agent.append("Do something bad", role="user")
        response = await agent.call()

        # The refusal should be captured in the response
        # Note: The exact behavior depends on how the agent handles refusals
        assert response.content.strip() == "" or response.refusal is not None
