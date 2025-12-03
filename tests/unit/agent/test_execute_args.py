import pytest
from good_agent import Agent
from good_agent.messages import AssistantMessage, UserMessage


class TestExecuteArgs:
    """Test that execute() accepts message arguments directly."""

    @pytest.mark.asyncio
    async def test_execute_with_message_args(self):
        """Test execute() with content arguments appends message before execution."""
        agent = Agent("System prompt")

        # Mock response
        with agent.mock(agent.mock.create("I heard you", role="assistant")) as mock_agent:
            # Execute with message content
            messages = []
            async for message in mock_agent.execute("Hello there"):
                messages.append(message)

            # Verify user message was appended
            assert len(mock_agent.agent.messages) == 2  # System + User
            assert isinstance(mock_agent.agent.messages[1], UserMessage)
            assert mock_agent.agent.messages[1].content == "Hello there"

            # Verify assistant response
            assert len(messages) == 1
            assert isinstance(messages[0], AssistantMessage)
            assert messages[0].content == "I heard you"

    @pytest.mark.asyncio
    async def test_execute_with_multiple_parts(self):
        """Test execute() with multiple content parts."""
        agent = Agent("System prompt")

        with agent.mock(agent.mock.create("Response", role="assistant")) as mock_agent:
            async for _ in mock_agent.execute("Part 1", "Part 2"):
                pass

            assert isinstance(mock_agent.agent.messages[1], UserMessage)
            # Content parts are typically joined or handled by the message class
            # Checking if it contains both parts
            assert "Part 1" in str(mock_agent.agent.messages[1].content)
            assert "Part 2" in str(mock_agent.agent.messages[1].content)

    @pytest.mark.asyncio
    async def test_call_delegation_to_execute(self):
        """Test that call() delegates to execute() and handles messages correctly."""
        agent = Agent("System prompt")

        with agent.mock(agent.mock.create("Response", role="assistant")) as mock_agent:
            # usage with message args
            response = await mock_agent.call("Hello call")

            assert response.content == "Response"
            assert isinstance(mock_agent.agent.messages[1], UserMessage)
            assert mock_agent.agent.messages[1].content == "Hello call"
