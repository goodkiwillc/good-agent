import pytest
from unittest.mock import MagicMock
from good_agent.agent.core import Agent
from good_agent.extensions.agent_tool import AgentAsTool
from good_agent.mock import mock_message


@pytest.mark.asyncio
async def test_agent_as_tool_initialization():
    """Test that AgentAsTool initializes correctly."""
    mock_agent = MagicMock(spec=Agent)
    mock_agent.name = "test_agent"

    tool_wrapper = AgentAsTool(mock_agent)

    assert tool_wrapper.base_agent == mock_agent
    assert tool_wrapper.name == "test_agent"
    assert tool_wrapper.description == "Delegate task to test_agent"
    assert tool_wrapper.multi_turn is True
    assert tool_wrapper.sessions == {}


@pytest.mark.asyncio
async def test_agent_as_tool_custom_params():
    """Test initialization with custom name and description."""
    mock_agent = MagicMock(spec=Agent)

    tool_wrapper = AgentAsTool(
        mock_agent,
        name="custom_tool",
        description="Custom description",
        multi_turn=False,
    )

    assert tool_wrapper.name == "custom_tool"
    assert tool_wrapper.description == "Custom description"
    assert tool_wrapper.multi_turn is False


@pytest.mark.asyncio
async def test_as_tool_returns_tool_instance():
    """Test that as_tool returns a configured Tool instance."""
    mock_agent = MagicMock(spec=Agent)
    mock_agent.name = "test_agent"

    tool_wrapper = AgentAsTool(mock_agent)
    tool = tool_wrapper.as_tool()

    assert tool.name == "test_agent"
    assert tool.description == "Delegate task to test_agent"
    # Verify parameters are manually injected correctly
    assert "prompt" in tool._tool_metadata.parameters
    assert "session_id" in tool._tool_metadata.parameters
    assert tool._tool_metadata.parameters["prompt"].type is str
    assert tool._tool_metadata.parameters["session_id"].required is False


@pytest.mark.asyncio
async def test_call_one_shot():
    """Test one-shot execution (no session ID)."""
    mock_agent = MagicMock(spec=Agent)
    # Setup fork to return a mock agent that can be called
    mock_forked_agent = MagicMock(spec=Agent)

    # Configure the async call method on the forked agent
    async def mock_call(*args, **kwargs):
        return mock_message("Response content", role="assistant")

    mock_forked_agent.call = mock_call

    mock_agent.fork.return_value = mock_forked_agent

    tool_wrapper = AgentAsTool(mock_agent)

    response = await tool_wrapper(prompt="Hello")

    assert response == "Response content"
    mock_agent.fork.assert_called_once_with(include_messages=True)
    # Should not store session
    assert len(tool_wrapper.sessions) == 0


@pytest.mark.asyncio
async def test_call_multi_turn_new_session():
    """Test multi-turn execution with a new session ID."""
    mock_agent = MagicMock(spec=Agent)
    mock_forked_agent = MagicMock(spec=Agent)

    async def mock_call(*args, **kwargs):
        return mock_message("Session response", role="assistant")

    mock_forked_agent.call = mock_call

    mock_agent.fork.return_value = mock_forked_agent

    tool_wrapper = AgentAsTool(mock_agent, multi_turn=True)

    response = await tool_wrapper(prompt="Hello", session_id="session_1")

    assert response == "Session response"
    mock_agent.fork.assert_called_once_with(include_messages=True)
    assert "session_1" in tool_wrapper.sessions
    assert tool_wrapper.sessions["session_1"] == mock_forked_agent


@pytest.mark.asyncio
async def test_call_multi_turn_existing_session():
    """Test multi-turn execution reusing an existing session."""
    mock_agent = MagicMock(spec=Agent)
    mock_forked_agent = MagicMock(spec=Agent)

    call_mock = MagicMock()

    async def mock_call(*args, **kwargs):
        call_mock(*args, **kwargs)
        return mock_message("Follow-up response", role="assistant")

    mock_forked_agent.call = mock_call

    # Pre-populate session
    tool_wrapper = AgentAsTool(mock_agent, multi_turn=True)
    tool_wrapper.sessions["session_1"] = mock_forked_agent

    response = await tool_wrapper(prompt="Follow up", session_id="session_1")

    assert response == "Follow-up response"
    # Should NOT fork again
    mock_agent.fork.assert_not_called()
    call_mock.assert_called_once_with("Follow up")


@pytest.mark.asyncio
async def test_call_multi_turn_disabled():
    """Test that session ID is ignored when multi_turn is False."""
    mock_agent = MagicMock(spec=Agent)
    mock_forked_agent = MagicMock(spec=Agent)

    async def mock_call(*args, **kwargs):
        return mock_message("One-shot response", role="assistant")

    mock_forked_agent.call = mock_call

    mock_agent.fork.return_value = mock_forked_agent

    tool_wrapper = AgentAsTool(mock_agent, multi_turn=False)

    response = await tool_wrapper(prompt="Hello", session_id="session_1")

    assert response == "One-shot response"
    # Should fork because it treats it as one-shot
    mock_agent.fork.assert_called_once_with(include_messages=True)
    # Should NOT store session
    assert "session_1" not in tool_wrapper.sessions
