import pytest
from good_agent import Agent
from good_agent.messages import SystemMessage


class TestSystemMessageVersioningFix:
    """Tests to drive the fix for system message versioning."""

    @pytest.mark.asyncio
    async def test_system_message_creates_initial_version(self):
        """System message from constructor should create version."""
        agent = Agent("You are helpful")
        await agent.initialize()

        # Should have one version for the system message
        assert agent._version_manager.version_count == 1, (
            "System message should create initial version"
        )
        assert len(agent.current_version) == 1, (
            "Current version should contain system message ID"
        )

        # System message should be in registry
        sys_msg = agent.messages[0]
        assert isinstance(sys_msg, SystemMessage)
        retrieved = agent._message_registry.get(sys_msg.id)
        assert retrieved is not None, "System message should be registered"
        assert retrieved.id == sys_msg.id

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_replace_system_message_creates_version(self):
        """Replacing system message should create new version."""
        agent = Agent("Original prompt")
        await agent.initialize()

        # Add a user message to establish versioning
        agent.append("Hello")

        # Get initial state
        initial_version_count = agent._version_manager.version_count
        original_sys_msg_id = agent.messages[0].id

        # Replace system message
        agent.set_system_message("New prompt")

        # Should create new version
        assert agent._version_manager.version_count == initial_version_count + 1, (
            "Replacing system message should create new version"
        )

        # New system message should have different ID
        new_sys_msg = agent.messages[0]
        assert isinstance(new_sys_msg, SystemMessage)
        assert new_sys_msg.id != original_sys_msg_id, (
            "New system message should have different ID"
        )

        # Both system messages should be in registry
        assert agent._message_registry.get(original_sys_msg_id) is not None, (
            "Original system message should be preserved in registry"
        )
        assert agent._message_registry.get(new_sys_msg.id) is not None, (
            "New system message should be in registry"
        )

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_add_system_message_to_empty_agent(self):
        """Adding system message to empty agent should version."""
        agent = Agent()  # No system message
        await agent.initialize()

        # Verify empty state
        assert len(agent.messages) == 0
        assert agent._version_manager.version_count == 0

        # Add system message
        agent.set_system_message("System prompt")

        # Should create version
        assert agent._version_manager.version_count == 1, (
            "Adding system message should create version"
        )
        assert len(agent.current_version) == 1, (
            "Version should contain system message ID"
        )
        assert len(agent.messages) == 1
        assert isinstance(agent.messages[0], SystemMessage)

        # Should be in registry
        sys_msg = agent.messages[0]
        assert agent._message_registry.get(sys_msg.id) is not None

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_revert_preserves_system_message(self):
        """Reverting should maintain system message in version."""
        agent = Agent("System prompt")
        await agent.initialize()

        # Add messages to establish versioning
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Should have versions now
        assert agent._version_manager.version_count >= 3

        # Revert to version with just first user message
        # (This should be version 1: system + message 1)
        agent.revert_to_version(1)

        # Should have system message + first user message
        assert len(agent.messages) == 2, (
            "Should have system message and first user message"
        )
        assert isinstance(agent.messages[0], SystemMessage), (
            "First message should be system message after revert"
        )
        assert "Message 1" in str(agent.messages[1]), (
            "Second message should be 'Message 1'"
        )

        # System message should still be the same
        assert "System prompt" in str(agent.messages[0])

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_multiple_system_message_updates_tracked(self):
        """Multiple system message updates should all be versioned."""
        agent = Agent("Initial prompt")
        await agent.initialize()

        # Add a user message
        agent.append("User message")

        # Update system message multiple times
        agent.set_system_message("Second prompt")
        version_after_second = agent._version_manager.version_count

        agent.set_system_message("Third prompt")
        version_after_third = agent._version_manager.version_count

        agent.set_system_message("Fourth prompt")
        version_after_fourth = agent._version_manager.version_count

        # Each update should create a new version
        assert version_after_third > version_after_second, (
            "Each system message update should create version"
        )
        assert version_after_fourth > version_after_third, (
            "Each system message update should create version"
        )

        # Should be able to revert to any version
        agent.revert_to_version(version_after_second - 1)
        assert "Second prompt" in str(agent.messages[0])

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_system_message_versioning_with_thread_context(self):
        """ThreadContext should work with system message versioning."""
        agent = Agent("Original system")
        await agent.initialize()

        agent.append("Message 1")
        agent.append("Message 2")

        # Use thread context to modify system message
        async with agent.context_manager.thread_context() as ctx:
            # Replace system message in context
            ctx.set_system_message("Temporary system")

            # Should have new system message in context
            assert "Temporary system" in str(ctx.messages[0])

            # Add a message
            ctx.append("Context message")

        # After context, should have original system message
        # but with the new user message added
        assert "Original system" in str(agent.messages[0]), (
            "Original system message should be restored"
        )
        assert "Context message" in str(agent.messages[-1]), (
            "Context message should be preserved"
        )

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_system_message_versioning_with_fork(self):
        """Forked agents should properly version system messages."""
        agent = Agent("Original system")
        await agent.initialize()

        agent.append("Original message")

        # Fork the agent
        forked = agent.context_manager.fork(include_messages=True)
        await forked.initialize()

        # Modify system message in fork
        forked.set_system_message("Forked system")

        # Fork should have new system message
        assert "Forked system" in str(forked.messages[0])

        # Original should be unchanged
        assert "Original system" in str(agent.messages[0])

        # Both should have proper versioning
        assert forked._version_manager.version_count > 0
        assert agent._version_manager.version_count >= 0

        await agent.events.async_close()
        await forked.async_close()
