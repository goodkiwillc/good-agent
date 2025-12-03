import pytest
from good_agent import Agent, tool
from good_agent.content.parts import TextContentPart
from good_agent.messages import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


class TestBranchMessageReplacement:
    """Test branch() with message replacement scenarios."""

    @pytest.mark.asyncio
    async def test_branch_truncates_tool_messages(self):
        """Test that branch() can truncate tool messages and restore them."""

        # Create agent with a tool
        @tool
        def search(query: str) -> str:
            """Search for information."""
            return f"Results for: {query}"

        agent = Agent("You are a helpful assistant", tools=[search])
        await agent.initialize()

        # Build conversation with tool calls
        agent.append("Search for Python tutorials")
        agent.append("I'll search for Python tutorials", role="assistant")

        # Simulate tool call and response (what would happen in execute())
        # Assistant message with tool_calls
        tool_call_msg = AssistantMessage(
            content_parts=[],
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "search",
                        "arguments": '{"query": "Python tutorials"}',
                    },
                }
            ],
        )
        agent.messages.append(tool_call_msg)

        # Tool response message
        tool_response_msg: ToolMessage = ToolMessage(
            tool_call_id="call_123",
            tool_name="search",
            content="Results for: Python tutorials - 10 tutorials found",
        )
        agent.messages.append(tool_response_msg)

        agent.append("Here are 10 Python tutorials I found...", role="assistant")

        # Capture original state
        original_message_count = len(agent.messages)
        assert (
            original_message_count == 6
        )  # system + user + assistant + tool_call + tool_response + assistant
        original_last_msg = agent.messages[-1]

        # Use branch to truncate before tool messages
        async with agent.branch(truncate_at=3) as ctx:
            # Should only have system + first user + first assistant
            assert len(ctx.messages) == 3
            assert isinstance(ctx.messages[0], SystemMessage)
            assert isinstance(ctx.messages[1], UserMessage)
            assert isinstance(ctx.messages[2], AssistantMessage)

            # Tool messages should be truncated
            assert not any(
                isinstance(msg, AssistantMessage) and msg.tool_calls for msg in ctx.messages
            )
            assert not any(isinstance(msg, ToolMessage) for msg in ctx.messages)

            # Add new message in truncated context
            ctx.append("Actually, can you search for JavaScript instead?")
            ctx.append("I'll search for JavaScript tutorials", role="assistant")

            assert len(ctx.messages) == 5  # 3 truncated + 2 new

        # After context: original messages restored + new messages appended
        assert len(agent.messages) == original_message_count + 2

        # Verify original tool messages are still there
        assert isinstance(agent.messages[3], AssistantMessage) and agent.messages[3].tool_calls
        assert isinstance(agent.messages[4], ToolMessage)
        assert agent.messages[5] == original_last_msg

        # New messages appended at the end
        assert "JavaScript" in str(agent.messages[-2])
        assert "JavaScript" in str(agent.messages[-1])

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_branch_replace_messages_before_fork(self):
        """Test replacing messages before the fork point in branch()."""
        agent = Agent("You are a helpful assistant")
        await agent.initialize()

        # Build conversation
        agent.append("Message 1")
        agent.append("Response 1", role="assistant")
        agent.append("Message 2")
        agent.append("Response 2", role="assistant")
        agent.append("Message 3")
        agent.append("Response 3", role="assistant")

        # Capture original message IDs
        original_ids = [msg.id for msg in agent.messages]
        original_version_count = agent._version_manager.version_count

        # Use Branch to truncate at message 2 (account for system message)
        async with agent.branch(truncate_at=5) as ctx:
            # Should have system + first 4 messages (up to Response 2)
            assert len(ctx.messages) == 5

            # Replace the last message before truncation
            old_msg = ctx.messages[4]
            ctx.messages[4] = AssistantMessage(
                content_parts=[TextContentPart(text="Modified Response 2")]
            )

            # The replacement should create a new version
            assert ctx._version_manager.version_count > original_version_count

            # Old message should be preserved in registry
            assert ctx._message_registry.get(old_msg.id) is not None

            # Add new messages after the replacement
            ctx.append("New Message in Context")
            ctx.append("New Response in Context", role="assistant")

            assert len(ctx.messages) == 7  # system + 4 truncated (1 replaced) + 2 new

        # After context: original messages restored + new messages
        assert len(agent.messages) == 9  # system + 6 original + 2 new

        # Original messages should be intact (including the one we replaced in context)
        for i in range(7):
            assert agent.messages[i].id == original_ids[i]

        # Specifically check that Response 2 is unmodified
        assert "Response 2" in str(agent.messages[4])
        assert "Modified" not in str(agent.messages[4])

        # New messages should be appended
        assert "New Message in Context" in str(agent.messages[7])
        assert "New Response in Context" in str(agent.messages[8])

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_branch_multiple_truncations(self):
        """Test multiple nested truncations with Branch."""
        agent = Agent("You are a helpful assistant")
        await agent.initialize()

        # Build a longer conversation
        for i in range(1, 6):
            agent.append(f"User message {i}")
            agent.append(f"Assistant response {i}", role="assistant")

        # system + 10 messages total
        assert len(agent.messages) == 11
        original_ids = [msg.id for msg in agent.messages]

        # First context: truncate to system + 6 messages
        async with agent.branch(truncate_at=7) as ctx1:
            assert len(ctx1.messages) == 7

            # Modify in first context
            ctx1.append("Context 1 message")
            assert len(ctx1.messages) == 8

            # Nested context: further truncate to system + 4
            async with ctx1.branch(truncate_at=5) as ctx2:
                assert len(ctx2.messages) == 5

                # Replace a message in nested context
                ctx2.messages[4] = AssistantMessage(
                    content_parts=[TextContentPart(text="Deeply modified")]
                )

                # Add in nested context
                ctx2.append("Context 2 message")
                assert len(ctx2.messages) == 6

            # Back in ctx1: should have ctx1 state + nested additions
            assert len(ctx1.messages) == 9  # system + 6 + context1 + context2

        # Back in main: should have original + both context additions
        assert len(agent.messages) == 13  # system + 10 original + 2 additions

        # Original messages preserved
        for i in range(11):
            assert agent.messages[i].id == original_ids[i]

        # Context messages appended
        assert "Context 1 message" in str(agent.messages[11])
        assert "Context 2 message" in str(agent.messages[12])

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_branch_with_version_revert(self):
        """Test Branch combined with version reverting."""
        agent = Agent("You are a helpful assistant")
        await agent.initialize()

        # Build conversation
        agent.append("Original 1")
        agent.append("Original 2")
        agent.append("Original 3")

        # Capture version after original messages
        version_after_original = agent._version_manager.version_count

        # Add more messages
        agent.append("Extra 1")
        agent.append("Extra 2")

        assert len(agent.messages) == 6  # system + 5 user messages

        # Use Branch
        async with agent.branch() as ctx:
            # Revert to original state within context
            ctx.revert_to_version(version_after_original - 1)

            # Should have system + original 3 messages
            assert len(ctx.messages) == 4
            assert "Original 3" in str(ctx.messages[-1])

            # Add new message in reverted state
            ctx.append("Added after revert")
            assert len(ctx.messages) == 5

        # After context: Branch without truncate_at restores original state
        # Since we reverted to 4 and added 1 (=5), which is less than original 6,
        # no new messages are appended beyond the original
        assert len(agent.messages) == 6

        # Extra messages should still be there
        assert "Extra 1" in str(agent.messages[4])
        assert "Extra 2" in str(agent.messages[5])

        # The message added after revert is NOT appended because it was added
        # at position 5, which is within the original message count
        assert "Added after revert" not in str(agent.messages)

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_isolated_preserves_original(self):
        """Test that Isolated completely isolates changes."""
        agent = Agent("You are a helpful assistant")
        await agent.initialize()

        # Build conversation with tool-like messages
        agent.append("User request")
        agent.append("I'll help with that", role="assistant")
        agent.append("[Tool execution details]")  # Simulate tool message
        agent.append("[Tool results]")  # Simulate tool response
        agent.append("Based on the results...", role="assistant")

        original_count = len(agent.messages)
        original_ids = [msg.id for msg in agent.messages]

        # Use Isolated to create isolated changes
        async with agent.isolated(truncate_at=3) as fork:
            # Fork only has system + first 2 messages
            assert len(fork.messages) == 3

            # Completely replace messages in fork (keeping system)
            while len(fork.messages) > 1:  # Keep system message
                fork.messages.pop()
            fork.append("Completely different conversation")
            fork.append("Completely different response", role="assistant")

            assert len(fork.messages) == 3  # system + 2 new

            # These changes only exist in fork
            assert fork._version_manager is not agent._version_manager

        # After fork: original completely unchanged
        assert len(agent.messages) == original_count

        # All original messages intact
        for i, msg_id in enumerate(original_ids):
            assert agent.messages[i].id == msg_id

        # No contamination from fork
        assert "Completely different" not in str(agent.messages)

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_branch_with_system_message_replacement(self):
        """Test that system messages can be replaced in Branch."""
        agent = Agent("Original system prompt")
        await agent.initialize()

        agent.append("User message")
        agent.append("Assistant response", role="assistant")

        original_system = agent.messages[0]

        # Use Branch to replace system message
        async with agent.branch() as ctx:
            # Replace system message in context
            ctx.messages[0] = SystemMessage(
                content_parts=[TextContentPart(text="Modified system prompt")]
            )

            # Verify replacement in context
            assert "Modified system prompt" in str(ctx.messages[0])
            assert ctx.messages[0].id != original_system.id

            # Add message with modified system context
            ctx.append("Message with modified system")
            ctx.append("Response with modified system", role="assistant")

        # After context: original system message restored
        assert agent.messages[0].id == original_system.id
        assert "Original system prompt" in str(agent.messages[0])

        # New messages appended
        assert "Message with modified system" in str(agent.messages[-2])
        assert "Response with modified system" in str(agent.messages[-1])

        await agent.events.close()
