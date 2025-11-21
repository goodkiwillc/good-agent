import pytest
from good_agent import Agent


class TestConversationLifecycle:
    """Test suite for conversation lifecycle management."""

    @pytest.mark.asyncio
    async def test_inline_lifecycle_management(self):
        """Test that Conversation manages lifecycle of uninitialized agents."""

        # Create agents without entering their context
        agent1 = Agent("Agent 1", name="agent1")
        agent2 = Agent("Agent 2", name="agent2")

        assert not agent1.is_ready
        assert not agent2.is_ready

        # Use conversation context
        async with agent1 | agent2 as conversation:
            # Agents should be ready now
            assert agent1.is_ready
            assert agent2.is_ready
            assert conversation._active

        # Verify conversation is inactive
        assert not conversation._active

    @pytest.mark.asyncio
    async def test_mixed_lifecycle_management(self):
        """Test mixing initialized and uninitialized agents."""
        async with Agent("Parent managed", name="parent_managed") as parent_agent:
            assert parent_agent.is_ready

            unmanaged_agent = Agent("Self managed", name="unmanaged")
            assert not unmanaged_agent.is_ready

            async with parent_agent | unmanaged_agent:
                assert parent_agent.is_ready
                assert unmanaged_agent.is_ready

            # Parent agent should STILL be ready/open and usable
            assert parent_agent.is_ready

            # Verify parent agent still works (e.g. append message)
            parent_agent.append("Test message")
            assert parent_agent.messages[-1].content == "Test message"
