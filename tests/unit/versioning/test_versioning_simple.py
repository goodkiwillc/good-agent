import pytest
from good_agent import Agent
from good_agent.messages import AssistantMessage, SystemMessage, UserMessage


class TestSimpleVersioning:
    """Basic versioning tests without mocking."""

    @pytest.mark.asyncio
    async def test_agent_append_creates_versions(self):
        """Test that appending messages creates versions."""
        # Create agent without system message
        agent = Agent()
        await agent.ready()

        # Initially no versions
        assert agent._version_manager.version_count == 0
        assert len(agent.messages) == 0

        # Add first message
        agent.append("First message")
        assert agent._version_manager.version_count == 1
        assert len(agent.messages) == 1

        # Add second message
        agent.append("Second message")
        assert agent._version_manager.version_count == 2
        assert len(agent.messages) == 2

        # Verify messages are in registry
        for msg in agent.messages:
            retrieved = agent._message_registry.get(msg.id)
            assert retrieved is not None
            assert retrieved.id == msg.id

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_system_message_versioning(self):
        """Test versioning with system message.

        System messages added via constructor/set_system_message now properly
        participate in versioning after the fix was implemented.
        """
        # Create agent with system message
        agent = Agent("You are a helpful assistant")
        await agent.ready()

        # System message now creates initial version (fixed!)
        assert agent._version_manager.version_count == 1
        assert len(agent.messages) == 1
        assert isinstance(agent.messages[0], SystemMessage)

        # Version contains the system message
        version_ids = agent._version_manager.current_version
        assert len(version_ids) == 1  # System message is versioned

        # System message should be in registry
        sys_msg = agent.messages[0]
        assert agent._message_registry.get(sys_msg.id) is not None

        # Add user message - this creates second version
        agent.append("Hello")
        assert agent._version_manager.version_count == 2
        assert len(agent.messages) == 2

        # Current version contains both system and user message
        version_ids = agent._version_manager.current_version
        assert len(version_ids) == 2  # Both messages versioned

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_message_replacement_versioning(self):
        """Test that replacing messages creates new versions."""
        agent = Agent()
        await agent.ready()

        # Add initial messages
        agent.append("First")
        agent.append("Second")
        assert agent._version_manager.version_count == 2

        # Replace first message
        old_id = agent.messages[0].id
        agent.messages[0] = UserMessage(content_parts=[])
        new_id = agent.messages[0].id

        # Should create new version
        assert agent._version_manager.version_count == 3
        assert old_id != new_id

        # Both messages should be in registry
        assert agent._message_registry.get(old_id) is not None
        assert agent._message_registry.get(new_id) is not None

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_revert_to_version(self):
        """Test reverting to earlier versions."""
        agent = Agent()
        await agent.ready()

        # Build version history
        agent.append("v1")
        agent.append("v2")
        agent.append("v3")

        assert len(agent.messages) == 3
        assert agent._version_manager.version_count == 3

        # Revert to version 1 (just "v1" and "v2")
        agent.revert_to_version(1)

        # Should create new version, not destroy old ones
        assert agent._version_manager.version_count == 4
        assert len(agent.messages) == 2
        assert "v1" in str(agent.messages[0])
        assert "v2" in str(agent.messages[1])

        # All messages still in registry
        for i in range(3):
            version_ids = agent._version_manager.get_version(i)
            for msg_id in version_ids:
                assert agent._message_registry.get(msg_id) is not None

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_thread_context_basic(self):
        """Test basic thread context functionality."""
        agent = Agent()
        await agent.ready()

        # Add messages
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Use thread context to truncate
        async with agent.thread_context(truncate_at=2) as ctx:
            # Should only see first 2 messages
            assert len(ctx.messages) == 2

            # Add new message
            ctx.append("New message")
            assert len(ctx.messages) == 3

        # After context: original 3 + new message
        assert len(agent.messages) == 4
        assert "Message 3" in str(agent.messages[2])
        assert "New message" in str(agent.messages[3])

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_fork_context_basic(self):
        """Test basic fork context functionality."""
        agent = Agent()
        await agent.ready()

        agent.append("Original message")
        original_count = len(agent.messages)

        # Use fork context
        async with agent.fork_context() as forked:
            assert forked is not agent
            assert len(forked.messages) == original_count

            # Add to fork
            forked.append("Fork only")
            assert len(forked.messages) == original_count + 1

        # Original unchanged
        assert len(agent.messages) == original_count

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_clear_messages(self):
        """Test that clearing messages creates empty version."""
        agent = Agent()
        await agent.ready()

        # Add messages
        agent.append("Message 1")
        agent.append("Message 2")
        assert agent._version_manager.version_count == 2

        # Clear messages
        agent.messages.clear()

        # Should create empty version
        assert agent._version_manager.version_count == 3
        assert agent._version_manager.current_version == []
        assert len(agent.messages) == 0

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_extend_messages(self):
        """Test that extend creates single version."""
        agent = Agent()
        await agent.ready()

        # Add initial message
        agent.append("First")
        assert agent._version_manager.version_count == 1

        # Extend with multiple messages
        new_messages = [
            UserMessage(content_parts=[]),
            AssistantMessage(content_parts=[]),
        ]
        agent.messages.extend(new_messages)

        # Should create only one new version
        assert agent._version_manager.version_count == 2
        assert len(agent.messages) == 3

        # All messages in registry
        for msg in agent.messages:
            assert agent._message_registry.get(msg.id) is not None

        await agent.async_close()
