from typing import Any, cast

import pytest
from good_agent import (
    Agent,
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


@pytest.mark.asyncio
async def test_agent_setitem_single_index():
    """Test setting a single message by index."""
    async with Agent("Initial system") as agent:
        agent.append("First message")
        agent.append("Second message")

        # Replace the first user message
        new_msg = UserMessage(content="Replaced first")
        agent[1] = new_msg

        assert agent[1].content == "Replaced first"
        assert len(agent) == 3  # System + 2 user messages


@pytest.mark.asyncio
async def test_agent_setitem_slice():
    """Test setting multiple messages with a slice."""
    async with Agent("System") as agent:
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Replace messages 2 and 3
        new_messages = [UserMessage(content="New 2"), UserMessage(content="New 3")]
        agent[2:4] = new_messages

        assert agent[2].content == "New 2"
        assert agent[3].content == "New 3"
        assert len(agent) == 4


@pytest.mark.asyncio
async def test_agent_setitem_list_indices():
    """Test setting messages at specific indices using a list."""
    async with Agent("System") as agent:
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")
        agent.append("Message 4")

        # Replace messages at indices 1 and 3
        new_messages = [
            UserMessage(content="Replaced 1"),
            UserMessage(content="Replaced 3"),
        ]
        agent[[1, 3]] = new_messages

        assert agent[1].content == "Replaced 1"
        assert agent[2].content == "Message 2"  # Unchanged
        assert agent[3].content == "Replaced 3"
        assert len(agent) == 5


@pytest.mark.asyncio
async def test_agent_setitem_negative_indexing():
    """Test setting messages with negative indices."""
    async with Agent("System") as agent:
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Replace the last message
        agent[-1] = UserMessage(content="Last replaced")

        assert agent[-1].content == "Last replaced"
        assert agent[3].content == "Last replaced"


@pytest.mark.asyncio
async def test_agent_setitem_system_message():
    """Test replacing the system message."""
    async with Agent("Original system") as agent:
        agent.append("User message")

        # Replace system message at index 0
        new_system = SystemMessage(content="New system prompt")
        agent[0] = new_system

        assert agent[0].content == "New system prompt"
        assert isinstance(agent[0], SystemMessage)


@pytest.mark.asyncio
async def test_agent_setitem_type_validation():
    """Test that only Message objects can be assigned."""
    async with Agent("System") as agent:
        agent.append("Message")

        # Try to assign a non-Message object
        with pytest.raises(TypeError, match="Can only assign Message objects"):
            agent[1] = cast(Any, "Not a message object")

        # Try to assign a list with non-Message objects
        with pytest.raises(TypeError, match="All values must be Message objects"):
            agent[1:2] = cast(list[Any], ["Not a message", UserMessage(content="Valid")])


@pytest.mark.asyncio
async def test_agent_setitem_index_validation():
    """Test index validation for assignments."""
    async with Agent("System") as agent:
        agent.append("Message 1")

        # Try to assign to an out-of-bounds index
        with pytest.raises(IndexError, match="out of range"):
            agent[10] = UserMessage(content="Too far")

        # Try to assign to negative index that's out of bounds
        with pytest.raises(IndexError, match="out of range"):
            agent[-10] = UserMessage(content="Too negative")


@pytest.mark.asyncio
async def test_agent_setitem_value_count_mismatch():
    """Test that the number of values must match the number of indices."""
    async with Agent("System") as agent:
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Try to assign 2 messages to 3 indices
        with pytest.raises(ValueError, match="Number of values .* must match number of indices"):
            agent[1:4] = [
                UserMessage(content="Only one"),
                UserMessage(content="Only two"),
            ]

        # Try to assign 3 messages to 2 indices
        with pytest.raises(ValueError, match="Number of values .* must match number of indices"):
            agent[[1, 2]] = [
                UserMessage(content="One"),
                UserMessage(content="Two"),
                UserMessage(content="Three"),
            ]


@pytest.mark.asyncio
async def test_agent_setitem_preserves_agent_reference():
    """Test that replaced messages get proper agent reference."""
    async with Agent("System") as agent:
        agent.append("Original message")

        # Replace with a new message
        new_msg = UserMessage(content="Replacement")
        agent[1] = new_msg

        # The message should now have an agent reference via the agent property
        assert agent[1].agent is not None
        assert agent[1].agent == agent


@pytest.mark.asyncio
async def test_agent_setitem_updates_version():
    """Test that replacing messages updates the agent version."""
    async with Agent("System") as agent:
        agent.append("Message 1")

        original_version = agent.version_id

        # Replace a message
        agent[1] = UserMessage(content="Replaced")

        # Version should be updated
        assert agent.version_id != original_version


@pytest.mark.asyncio
async def test_agent_setitem_with_assistant_and_tool_messages():
    """Test replacing different message types."""
    async with Agent("System") as agent:
        agent.append("User message")
        agent.append(AssistantMessage(content="Assistant response"))
        agent.append(
            ToolMessage(content="Tool result", tool_call_id="call_123", tool_name="test_tool")
        )

        # Replace the assistant message
        new_assistant = AssistantMessage(content="New assistant response")
        agent[2] = new_assistant

        assert agent[2].content == "New assistant response"
        assert isinstance(agent[2], AssistantMessage)

        # Replace the tool message
        new_tool: ToolMessage = ToolMessage(
            content="New tool result", tool_call_id="call_456", tool_name="another_tool"
        )
        agent[3] = new_tool

        assert agent[3].content == "New tool result"
        assert isinstance(agent[3], ToolMessage)


@pytest.mark.asyncio
async def test_agent_setitem_empty_slice():
    """Test assignment with an empty slice."""
    async with Agent("System") as agent:
        agent.append("Message 1")
        agent.append("Message 2")

        # Empty slice should match empty list
        agent[2:2] = []

        # No changes should occur
        assert len(agent) == 3
        assert agent[1].content == "Message 1"
        assert agent[2].content == "Message 2"


@pytest.mark.asyncio
async def test_agent_setitem_single_message_to_slice():
    """Test assigning a single message (not in a list) to a single-element slice."""
    async with Agent("System") as agent:
        agent.append("Message 1")
        agent.append("Message 2")

        # Single message assigned to single-element slice
        agent[1:2] = UserMessage(content="Single replacement")

        assert agent[1].content == "Single replacement"
        assert len(agent) == 3


@pytest.mark.asyncio
async def test_agent_setitem_maintains_message_store():
    """Test that replaced messages are properly stored in the message store."""
    from good_agent.messages.store import message_store

    async with Agent("System") as agent:
        agent.append("Original")

        # Replace the message
        new_msg = UserMessage(content="Replaced")
        agent[1] = new_msg

        # The new message should be in the store
        stored_msg = message_store.get(agent[1].id)
        assert stored_msg is not None
        assert stored_msg.content == "Replaced"
