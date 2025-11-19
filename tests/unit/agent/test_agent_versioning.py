import pytest
import pytest_asyncio
from good_agent import Agent
from good_agent.agent.thread_context import ForkContext, ThreadContext
from good_agent.messages import AssistantMessage, SystemMessage, UserMessage
from good_agent.messages.versioning import MessageRegistry, VersionManager


class TestAgentVersioning:
    """Test Agent class with versioning integration."""

    @pytest_asyncio.fixture
    async def versioned_agent(self):
        """Agent with versioning enabled (default behavior)."""
        # Create agent without system prompt to have cleaner test state
        agent = Agent()
        await agent.initialize()
        return agent

    @pytest_asyncio.fixture
    async def agent_cleanup(self, versioned_agent):
        """Cleanup fixture for agents."""
        yield versioned_agent
        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_agent_initializes_versioning(self):
        """Agent should initialize versioning infrastructure by default."""
        agent = Agent("test")
        await agent.initialize()

        # Check versioning components exist
        assert hasattr(agent, "_message_registry")
        assert hasattr(agent, "_version_manager")
        assert isinstance(agent._message_registry, MessageRegistry)
        assert isinstance(agent._version_manager, VersionManager)

        # Check messages have versioning initialized
        assert agent._messages._registry is not None
        assert agent._messages._version_manager is not None

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_agent_append_creates_version(self, versioned_agent):
        """Agent.append should create new versions."""
        # Initially no versions (no messages yet)
        assert versioned_agent._version_manager.version_count == 0

        # Append first message
        versioned_agent.append("Hello")
        assert versioned_agent._version_manager.version_count == 1
        assert len(versioned_agent.messages) == 1

        # Append second message
        versioned_agent.append("World")
        assert versioned_agent._version_manager.version_count == 2
        assert len(versioned_agent.messages) == 2

        # Check version contains correct message IDs
        current_version = versioned_agent.current_version
        assert len(current_version) == 2
        assert current_version[0] == versioned_agent.messages[0].id
        assert current_version[1] == versioned_agent.messages[1].id

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_agent_message_replacement_preserves_old(self, versioned_agent):
        """Replacing a message should preserve the old one in registry."""
        versioned_agent.append("Original")
        original_id = versioned_agent.messages[0].id

        # Replace the message
        versioned_agent.messages[0] = UserMessage(content_parts=[])
        new_id = versioned_agent.messages[0].id

        assert original_id != new_id

        # Both messages exist in registry
        assert versioned_agent._message_registry.get(original_id) is not None
        assert versioned_agent._message_registry.get(new_id) is not None

        # New version created
        assert versioned_agent._version_manager.version_count == 2

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_agent_revert_to_version(self, versioned_agent):
        """Agent should support reverting to earlier versions."""
        versioned_agent.append("Message 1")
        versioned_agent.append("Message 2")
        versioned_agent.append("Message 3")

        # Should have 3 versions (one per append)
        assert versioned_agent._version_manager.version_count == 3

        # Revert to version with 2 messages
        versioned_agent.revert_to_version(1)

        # Should create new version (non-destructive)
        assert versioned_agent._version_manager.version_count == 4
        assert len(versioned_agent.messages) == 2
        assert "Message 2" in str(versioned_agent.messages[-1])

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_thread_context_manager(self, versioned_agent):
        """ThreadContext should allow temporary modifications."""
        versioned_agent.append("Message 1")
        versioned_agent.append("Message 2")
        versioned_agent.append("Message 3")

        len(versioned_agent.messages)

        async with ThreadContext(versioned_agent, truncate_at=2) as ctx_agent:
            # Should only see first 2 messages
            assert len(ctx_agent.messages) == 2
            assert ctx_agent is versioned_agent  # Same agent instance

            # Add a new message
            ctx_agent.append("Summary")
            assert len(ctx_agent.messages) == 3

        # After context: original 3 + summary
        assert len(versioned_agent.messages) == 4
        assert "Message 3" in str(versioned_agent.messages[2])
        assert "Summary" in str(versioned_agent.messages[3])

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_fork_context_manager(self, versioned_agent):
        """ForkContext should create isolated fork."""
        versioned_agent.append("Message 1")
        versioned_agent.append("Message 2")
        versioned_agent.append("Message 3")

        original_id = versioned_agent._id

        async with ForkContext(versioned_agent, truncate_at=2) as forked_agent:
            # Should be different agent
            assert forked_agent is not versioned_agent
            assert forked_agent._id != original_id

            # Should only have first 2 messages
            assert len(forked_agent.messages) == 2

            # Add message to fork
            forked_agent.append("Fork message")
            assert len(forked_agent.messages) == 3

        # Original unchanged
        assert len(versioned_agent.messages) == 3
        assert "Fork message" not in str(versioned_agent.messages)

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_agent_context_methods(self, versioned_agent):
        """Test convenience methods for context managers."""
        versioned_agent.append("Test")

        # Test thread_context method
        async with versioned_agent.context_manager.thread_context(truncate_at=0) as ctx:
            assert ctx is versioned_agent
            assert len(ctx.messages) == 0
            ctx.append("New")

        assert len(versioned_agent.messages) == 2

        # Test fork_context method
        async with versioned_agent.context_manager.fork_context(truncate_at=1) as fork:
            assert fork is not versioned_agent
            assert len(fork.messages) == 1

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_current_version_property(self, versioned_agent):
        """Test that current_version property works correctly."""
        # No messages, no version
        assert versioned_agent.current_version == []

        # Add messages
        versioned_agent.append("First")
        versioned_agent.append("Second")

        # Check current version
        version_ids = versioned_agent.current_version
        assert len(version_ids) == 2
        assert version_ids[0] == versioned_agent.messages[0].id
        assert version_ids[1] == versioned_agent.messages[1].id

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_version_tracking_across_operations(self, versioned_agent):
        """Test that versions are properly tracked across various operations."""
        # Initial state
        assert versioned_agent._version_manager.version_count == 0

        # Single append
        versioned_agent.append("One")
        assert versioned_agent._version_manager.version_count == 1

        # Multiple appends via extend
        versioned_agent.messages.extend(
            [UserMessage(content_parts=[]), AssistantMessage(content_parts=[])]
        )
        assert versioned_agent._version_manager.version_count == 2

        # Replacement
        versioned_agent.messages[0] = SystemMessage(content_parts=[])
        assert versioned_agent._version_manager.version_count == 3

        # Clear
        versioned_agent.messages.clear()
        assert versioned_agent._version_manager.version_count == 4
        assert versioned_agent.current_version == []

        await versioned_agent.events.close()

    @pytest.mark.asyncio
    async def test_message_registry_tracks_ownership(self, versioned_agent):
        """Registry should track which agent owns each message."""
        msg1 = UserMessage(content_parts=[])
        versioned_agent.append(msg1)

        # Check ownership
        owner = versioned_agent._message_registry.get_agent(msg1.id)
        assert owner is versioned_agent

        # Create another agent
        other_agent = Agent("other")
        await other_agent.initialize()

        msg2 = UserMessage(content_parts=[])
        other_agent.append(msg2)

        # Check different ownership
        owner2 = other_agent._message_registry.get_agent(msg2.id)
        assert owner2 is other_agent
        assert owner2 is not versioned_agent

        await versioned_agent.events.close()
        await other_agent.events.close()

    @pytest.mark.asyncio
    async def test_fork_inherits_versioning(self, versioned_agent):
        """Forked agents should have their own versioning."""
        versioned_agent.append("Original")

        # Fork the agent
        forked = versioned_agent.context_manager.fork(include_messages=True)
        await forked.initialize()

        # Forked agent should have its own version manager
        assert forked._version_manager is not versioned_agent._version_manager
        assert forked._message_registry is not versioned_agent._message_registry

        # But should have same message content
        assert len(forked.messages) == 1
        assert str(forked.messages[0]) == str(versioned_agent.messages[0])

        # Changes to fork don't affect original
        forked.append("Fork only")
        assert len(forked.messages) == 2
        assert len(versioned_agent.messages) == 1

        await versioned_agent.events.close()
        await forked.close()


class TestBackwardCompatibility:
    """Test that versioning doesn't break existing functionality."""

    @pytest.mark.asyncio
    async def test_agent_basic_operations_work(self):
        """All basic agent operations should work with versioning."""
        agent = Agent("test")
        await agent.initialize()

        initial_count = len(agent.messages)  # May have system message

        # Basic append
        agent.append("Hello")
        assert len(agent.messages) == initial_count + 1

        # List operations
        agent.messages[0] = SystemMessage(content_parts=[])
        assert isinstance(agent.messages[0], SystemMessage)

        # Filtering
        agent.append("User message", role="user")
        agent.append(AssistantMessage(content_parts=[]))

        user_msgs = agent.messages.filter(role="user")
        assert len(user_msgs) == 2  # "Hello" and "User message"

        # Properties
        assert len(agent.user) == 2
        assert len(agent.assistant) == 1
        assert len(agent.system) == 1

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_message_list_interface_preserved(self):
        """MessageList should maintain list interface."""
        agent = Agent()  # No system prompt for cleaner test
        await agent.initialize()

        msgs = agent.messages

        # List operations
        msg1 = UserMessage(content_parts=[])
        msgs.append(msg1)
        assert msg1 in msgs
        assert len(msgs) == 1

        # Indexing
        assert msgs[0] == msg1
        assert msgs[-1] == msg1

        # Slicing
        msg2 = AssistantMessage(content_parts=[])
        msgs.append(msg2)
        sliced = msgs[0:1]
        assert len(sliced) == 1
        assert sliced[0] == msg1

        # Iteration
        for i, msg in enumerate(msgs):
            assert msg == msgs[i]

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_fork_still_works(self):
        """Agent.fork() should work as before."""
        agent = Agent("original")
        await agent.initialize()

        agent.append("Message")

        # Fork without messages
        fork1 = agent.context_manager.fork(include_messages=False)
        await fork1.initialize()
        assert len(fork1.messages) == 0

        # Fork with messages
        fork2 = agent.context_manager.fork(include_messages=True)
        await fork2.initialize()
        assert len(fork2.messages) == 2  # System message + user message
        assert str(fork2.messages[-1]) == str(
            agent.messages[-1]
        )  # Last message matches

        await agent.events.close()
        await fork1.close()
        await fork2.close()
