import pytest
from good_agent import Agent
from good_agent.messages import (
    AssistantMessage,
    Message,
    MessageList,
    SystemMessage,
    UserMessage,
)
from good_agent.messages.versioning import MessageRegistry, VersionManager


class TestMessageListVersioning:
    """Test MessageList with versioning support."""

    def test_messagelist_without_versioning_works_normally(self):
        """Ensure backward compatibility when versioning not initialized."""
        messages: MessageList[Message] = MessageList()
        msg = SystemMessage(content_parts=[])
        messages.append(msg)

        assert len(messages) == 1
        assert messages[0] == msg

        # No versioning attributes should cause issues
        msg2 = UserMessage(content_parts=[])
        messages.append(msg2)
        assert len(messages) == 2

        # setitem should work
        msg3 = AssistantMessage(content_parts=[])
        messages[0] = msg3
        assert messages[0] == msg3
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_messagelist_with_versioning_creates_versions(self):
        """When versioning is initialized, operations create versions."""
        messages: MessageList[Message] = MessageList()
        registry = MessageRegistry()
        vm = VersionManager()

        # Create a real agent for proper testing
        agent = Agent("test")
        await agent.initialize()

        # Initialize versioning
        messages._init_versioning(registry, vm, agent)

        # Initially no versions
        assert vm.version_count == 0

        msg1 = SystemMessage(content_parts=[])
        messages.append(msg1)

        # Should create first version
        assert vm.version_count == 1
        assert vm.current_version == [msg1.id]
        assert registry.get(msg1.id) == msg1

        msg2 = UserMessage(content_parts=[])
        messages.append(msg2)

        # Should create second version
        assert vm.version_count == 2
        assert vm.current_version == [msg1.id, msg2.id]

        # Clean up
        await agent.events.close()

    @pytest.mark.asyncio
    async def test_messagelist_setitem_creates_new_version(self):
        """Setting an item should create a new version."""
        messages: MessageList[Message] = MessageList([SystemMessage(content_parts=[])])
        registry = MessageRegistry()
        vm = VersionManager()

        agent = Agent("test")
        await agent.initialize()

        messages._init_versioning(registry, vm, agent)

        # Initial version created during init
        assert vm.version_count == 1
        original_msg_id = messages[0].id

        new_msg = SystemMessage(content_parts=[])
        messages[0] = new_msg

        # Should create new version
        assert vm.version_count == 2
        assert vm.current_version == [new_msg.id]

        # Both messages should be in registry
        assert registry.get(original_msg_id) is not None
        assert registry.get(new_msg.id) is not None

        # Clean up
        await agent.events.close()

    @pytest.mark.asyncio
    async def test_sync_from_version_rebuilds_list(self):
        """_sync_from_version should rebuild list from version IDs."""
        messages: MessageList[Message] = MessageList()
        registry = MessageRegistry()
        vm = VersionManager()

        agent = Agent("test")
        await agent.initialize()

        # Setup: Add messages and create versions
        msg1 = SystemMessage(content_parts=[])
        msg2 = UserMessage(content_parts=[])
        msg3 = AssistantMessage(content_parts=[])

        messages._init_versioning(registry, vm, agent)
        messages.extend([msg1, msg2, msg3])

        assert vm.version_count == 1
        assert len(messages) == 3

        # Create another version with just first two messages
        vm.add_version([msg1.id, msg2.id])

        # Sync from the new version
        messages._sync_from_version()

        assert len(messages) == 2
        assert messages[0] == msg1
        assert messages[1] == msg2

        # Clean up
        await agent.events.close()

    @pytest.mark.asyncio
    async def test_extend_creates_single_version(self):
        """extend() should create only one new version for all messages."""
        messages: MessageList[Message] = MessageList()
        registry = MessageRegistry()
        vm = VersionManager()

        agent = Agent("test")
        await agent.initialize()

        messages._init_versioning(registry, vm, agent)

        # Add multiple messages at once
        msg1 = SystemMessage(content_parts=[])
        msg2 = UserMessage(content_parts=[])
        msg3 = AssistantMessage(content_parts=[])

        messages.extend([msg1, msg2, msg3])

        # Should create only one version
        assert vm.version_count == 1
        assert len(vm.current_version) == 3
        assert vm.current_version == [msg1.id, msg2.id, msg3.id]

        # All messages should be registered
        assert registry.get(msg1.id) == msg1
        assert registry.get(msg2.id) == msg2
        assert registry.get(msg3.id) == msg3

        # Clean up
        await agent.events.close()

    @pytest.mark.asyncio
    async def test_clear_creates_empty_version(self):
        """clear() should create an empty version."""
        messages: MessageList[Message] = MessageList()
        registry = MessageRegistry()
        vm = VersionManager()

        agent = Agent("test")
        await agent.initialize()

        # Start with some messages
        msg1 = SystemMessage(content_parts=[])
        msg2 = UserMessage(content_parts=[])

        messages._init_versioning(registry, vm, agent)
        messages.extend([msg1, msg2])

        assert vm.version_count == 1
        assert len(messages) == 2

        # Clear messages
        messages.clear()

        # Should create empty version
        assert vm.version_count == 2
        assert vm.current_version == []
        assert len(messages) == 0

        # Messages still in registry
        assert registry.get(msg1.id) == msg1
        assert registry.get(msg2.id) == msg2

        # Clean up
        await agent.events.close()

    @pytest.mark.asyncio
    async def test_slice_assignment_creates_version(self):
        """Slice assignment should create a new version."""
        messages: MessageList[Message] = MessageList()
        registry = MessageRegistry()
        vm = VersionManager()

        agent = Agent("test")
        await agent.initialize()

        # Start with some messages
        msg1 = SystemMessage(content_parts=[])
        msg2 = UserMessage(content_parts=[])
        msg3 = AssistantMessage(content_parts=[])

        messages._init_versioning(registry, vm, agent)
        messages.extend([msg1, msg2, msg3])

        assert vm.version_count == 1

        # Replace middle message using slice
        new_msg = UserMessage(content_parts=[])
        messages[1:2] = [new_msg]

        # Should create new version
        assert vm.version_count == 2
        assert len(messages) == 3
        assert messages[1] == new_msg
        assert vm.current_version == [msg1.id, new_msg.id, msg3.id]

        # All messages in registry
        assert registry.get(msg2.id) == msg2  # Original still there
        assert registry.get(new_msg.id) == new_msg

        # Clean up
        await agent.events.close()

    @pytest.mark.asyncio
    async def test_versioning_with_existing_messages(self):
        """Initializing versioning with existing messages should create initial version."""
        # Create list with existing messages
        msg1 = SystemMessage(content_parts=[])
        msg2 = UserMessage(content_parts=[])
        messages: MessageList[Message] = MessageList([msg1, msg2])

        assert len(messages) == 2

        registry = MessageRegistry()
        vm = VersionManager()

        agent = Agent("test")
        await agent.initialize()

        # Initialize versioning with existing messages
        messages._init_versioning(registry, vm, agent)

        # Should create initial version with existing messages
        assert vm.version_count == 1
        assert vm.current_version == [msg1.id, msg2.id]
        assert registry.get(msg1.id) == msg1
        assert registry.get(msg2.id) == msg2

        # Clean up
        await agent.events.close()

    @pytest.mark.asyncio
    async def test_agent_reference_maintained(self):
        """Agent reference should be maintained through versioning operations."""
        messages: MessageList[Message] = MessageList()
        registry = MessageRegistry()
        vm = VersionManager()

        agent = Agent("test")
        await agent.initialize()

        messages._init_versioning(registry, vm, agent)

        # Agent reference should be set
        assert messages.agent == agent

        # Add a message
        msg = SystemMessage(content_parts=[])
        messages.append(msg)

        # Check agent ownership in registry
        assert registry.get_agent(msg.id) == agent

        # Clean up
        await agent.events.close()

    def test_filter_maintains_list_type(self):
        """filter() should return MessageList, not affect versioning."""
        messages: MessageList[Message] = MessageList()

        # Add messages without versioning
        sys_msg = SystemMessage(content_parts=[])
        user_msg = UserMessage(content_parts=[])
        messages.extend([sys_msg, user_msg])

        # Filter should return MessageList
        filtered = messages.filter(role="system")
        assert isinstance(filtered, MessageList)
        assert len(filtered) == 1
        assert filtered[0] == sys_msg

        # Filtered list should not have versioning
        assert filtered._registry is None
        assert filtered._version_manager is None
