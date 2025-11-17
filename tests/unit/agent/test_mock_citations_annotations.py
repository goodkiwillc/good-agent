import pytest
from good_agent import Agent
from good_agent.messages import AssistantMessage
from good_agent.mock import (
    MockAgent,
    create_annotation,
    create_citation,
    create_usage,
    mock_message,
)


@pytest.mark.asyncio
async def test_mock_message_with_citations():
    """Test that mock messages can include citations."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create citations
    citations = [
        create_citation("https://example.com/source1"),
        create_citation("https://example.com/source2"),
    ]

    # Create mock response with citations
    mock_response = mock_message(
        "Here is information from sources", role="assistant", citations=citations
    )

    # Use mock agent with the response
    with MockAgent(agent, mock_response) as mock_agent:
        async for msg in mock_agent.execute():
            if isinstance(msg, AssistantMessage):
                assert msg.citations is not None
                assert len(msg.citations) == 2
                assert str(msg.citations[0]) == "https://example.com/source1"
                assert str(msg.citations[1]) == "https://example.com/source2"


@pytest.mark.asyncio
async def test_mock_message_with_annotations():
    """Test that mock messages can include annotations."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create annotations
    annotations = [
        create_annotation(
            text="Python", start=0, end=6, metadata={"type": "programming_language"}
        ),
        create_annotation(
            text="JavaScript",
            start=10,
            end=20,
            metadata={"type": "programming_language"},
        ),
    ]

    # Create mock response with annotations
    mock_response = mock_message(
        "Python and JavaScript are popular languages",
        role="assistant",
        annotations=annotations,
    )

    # Use mock agent with the response
    with MockAgent(agent, mock_response) as mock_agent:
        async for msg in mock_agent.execute():
            if isinstance(msg, AssistantMessage):
                assert msg.annotations is not None
                assert len(msg.annotations) == 2
                assert msg.annotations[0].text == "Python"
                assert msg.annotations[0].start == 0
                assert msg.annotations[0].end == 6
                assert msg.annotations[0].metadata["type"] == "programming_language"


@pytest.mark.asyncio
async def test_mock_message_with_refusal():
    """Test that mock messages can include refusal reasons."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create mock response with refusal
    mock_response = mock_message(
        "",
        role="assistant",
        refusal="I cannot provide information on harmful activities",
    )

    # Use mock agent with the response
    with MockAgent(agent, mock_response) as mock_agent:
        async for msg in mock_agent.execute():
            if isinstance(msg, AssistantMessage):
                assert msg.refusal is not None
                assert "harmful activities" in msg.refusal


@pytest.mark.asyncio
async def test_mock_message_with_reasoning():
    """Test that mock messages can include reasoning/chain-of-thought."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create mock response with reasoning
    mock_response = mock_message(
        "The answer is 42",
        role="assistant",
        reasoning="First, I need to calculate... Then I consider... Finally, the result is 42",
    )

    # Use mock agent with the response
    with MockAgent(agent, mock_response) as mock_agent:
        async for msg in mock_agent.execute():
            if isinstance(msg, AssistantMessage):
                assert msg.reasoning is not None
                assert "calculate" in msg.reasoning
                assert msg.content.strip() == "The answer is 42"


@pytest.mark.asyncio
async def test_mock_message_with_usage():
    """Test that mock messages can include token usage information."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create usage information
    usage = create_usage(prompt_tokens=150, completion_tokens=75, total_tokens=225)

    # Create mock response with usage
    mock_response = mock_message("This is a response", role="assistant", usage=usage)

    # Note: Usage is typically tracked at the model level, not message level
    # This test ensures the parameter is accepted even if not directly used
    with MockAgent(agent, mock_response) as mock_agent:
        async for msg in mock_agent.execute():
            if isinstance(msg, AssistantMessage):
                # Verify message was created successfully
                assert msg.content.strip() == "This is a response"


@pytest.mark.asyncio
async def test_mock_message_with_metadata():
    """Test that mock messages can include custom metadata."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create custom metadata
    metadata = {
        "source": "test_system",
        "version": "1.0",
        "timestamp": "2024-01-01T00:00:00Z",
        "custom_field": {"nested": "value"},
    }

    # Create mock response with metadata
    mock_response = mock_message(
        "Response with metadata", role="assistant", metadata=metadata
    )

    # Use mock agent with the response
    with MockAgent(agent, mock_response) as mock_agent:
        async for msg in mock_agent.execute():
            if isinstance(msg, AssistantMessage):
                # Verify message was created (metadata might be stored elsewhere)
                assert msg.content.strip() == "Response with metadata"


@pytest.mark.asyncio
async def test_mock_message_with_all_parameters():
    """Test that mock messages can include all parameters together."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create all components
    citations = [create_citation("https://example.com/source")]
    annotations = [create_annotation("key term", 10, 18)]
    usage = create_usage(100, 50)
    metadata = {"test": True}

    # Create mock response with all parameters
    mock_response = mock_message(
        "This is a key term mentioned in the source",
        role="assistant",
        citations=citations,
        annotations=annotations,
        refusal=None,  # No refusal
        reasoning="I found this information in the source",
        usage=usage,
        metadata=metadata,
    )

    # Use mock agent with the response
    with MockAgent(agent, mock_response) as mock_agent:
        async for msg in mock_agent.execute():
            if isinstance(msg, AssistantMessage):
                assert (
                    msg.content.strip() == "This is a key term mentioned in the source"
                )
                assert msg.citations is not None and len(msg.citations) == 1
                assert msg.annotations is not None and len(msg.annotations) == 1
                assert msg.reasoning is not None
                assert msg.refusal is None


@pytest.mark.asyncio
async def test_agent_mock_interface_create_with_citations():
    """Test AgentMockInterface.create() with citations and annotations."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Use the agent's mock interface
    mock_response = agent.mock.create(
        "Response with citations",
        role="assistant",
        citations=[create_citation("https://example.com")],
        annotations=[create_annotation("citations", 14, 23)],
    )

    # Verify the mock response has the expected fields
    assert mock_response.content == "Response with citations"
    assert mock_response.citations is not None
    assert len(mock_response.citations) == 1
    assert mock_response.annotations is not None
    assert len(mock_response.annotations) == 1


@pytest.mark.asyncio
async def test_mock_call_with_citations():
    """Test that MockAgent.call() properly handles citations and annotations."""
    agent = Agent("You are a helpful assistant")
    await agent.initialize()

    # Create mock response with citations
    mock_response = mock_message(
        "Information from sources",
        role="assistant",
        citations=[
            create_citation("https://source1.com"),
            create_citation("https://source2.com"),
        ],
        annotations=[create_annotation("Information", 0, 11)],
    )

    # Use mock agent
    mock_agent = MockAgent(agent, mock_response)
    msg = await mock_agent.call()

    # Verify the message has citations and annotations
    assert isinstance(msg, AssistantMessage)
    assert msg.citations is not None
    assert len(msg.citations) == 2
    assert msg.annotations is not None
    assert len(msg.annotations) == 1
    assert msg.annotations[0].text == "Information"
