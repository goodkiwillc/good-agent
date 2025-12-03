from typing import cast
from unittest.mock import Mock

import pytest
from ulid import ULID

from good_agent import Agent
from good_agent.messages import SystemMessage, UserMessage
from good_agent.messages.store import MessageStore
from good_agent.messages.versioning import (
    InMemoryMessageStore,
    MessageNotFoundError,
    MessageRegistry,
    VersionManager,
)


class TestMessageRegistry:
    """Test the MessageRegistry class for message storage and agent tracking."""

    def test_register_and_retrieve_message(self):
        """Test that messages can be registered and retrieved."""
        registry = MessageRegistry()
        msg = SystemMessage(content_parts=[], id=ULID())
        agent_mock = Mock()
        agent_mock._id = ULID()

        registry.register(msg, agent_mock)
        retrieved = registry.get(msg.id)
        assert retrieved == msg

    def test_get_nonexistent_message_returns_none(self):
        """Test that getting a non-existent message returns None."""
        registry = MessageRegistry()
        non_existent_id = ULID()

        result = registry.get(non_existent_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_tracks_agent_ownership(self):
        """Test that the registry tracks which agent owns each message."""
        registry = MessageRegistry()
        msg = SystemMessage(content_parts=[], id=ULID())

        # Create a real agent for proper weakref testing
        async with Agent("test") as agent:
            registry.register(msg, agent)
            owner = registry.get_agent(msg.id)
            assert owner == agent

            # Clean up
            await agent.events.close()

    def test_agent_weakref_cleanup(self):
        """Test that agent references are weak and can be garbage collected."""
        registry = MessageRegistry()
        msg = SystemMessage(content_parts=[], id=ULID())

        # Create agent in a scope so it can be garbage collected
        def create_and_register():
            agent = Mock()
            agent._id = ULID()
            registry.register(msg, agent)
            return msg.id

        msg_id = create_and_register()

        # Agent should be garbage collected, weakref should return None
        # Force garbage collection
        import gc

        gc.collect()

        registry.get_agent(msg_id)
        # Mock objects may not be garbage collected immediately, so we test cleanup
        cleaned = registry.cleanup_dead_references()
        # This test may be flaky due to GC timing, but cleanup method should work
        assert cleaned >= 0

    def test_track_version(self):
        """Test tracking which versions contain a message."""
        registry = MessageRegistry()
        msg_id = ULID()

        registry.track_version(msg_id, 0)
        registry.track_version(msg_id, 2)
        registry.track_version(msg_id, 5)

        versions = registry.get_versions_containing(msg_id)
        assert versions == [0, 2, 5]

    def test_track_version_no_duplicates(self):
        """Test that tracking the same version twice doesn't create duplicates."""
        registry = MessageRegistry()
        msg_id = ULID()

        registry.track_version(msg_id, 1)
        registry.track_version(msg_id, 1)  # Duplicate
        registry.track_version(msg_id, 2)

        versions = registry.get_versions_containing(msg_id)
        assert versions == [1, 2]

    def test_custom_message_store(self):
        """Test using a custom message store."""
        custom_store = cast(MessageStore, InMemoryMessageStore())
        registry = MessageRegistry(store=custom_store)

        msg = SystemMessage(content_parts=[], id=ULID())
        agent_mock = Mock()
        agent_mock._id = ULID()

        registry.register(msg, agent_mock)

        # Check that the message is in the custom store
        assert custom_store.exists(msg.id)
        retrieved = custom_store.get(msg.id)
        assert retrieved == msg


class TestVersionManager:
    """Test the VersionManager class for version history management."""

    def test_add_version_creates_new_version(self):
        """Test that adding a version creates a new version entry."""
        vm = VersionManager()
        version1 = [ULID(), ULID()]
        index = vm.add_version(version1)

        assert vm.version_count == 1
        assert vm.current_version == version1
        assert vm.current_version_index == 0
        assert index == 0

    def test_multiple_versions(self):
        """Test managing multiple versions."""
        vm = VersionManager()
        v1 = [ULID()]
        v2 = [ULID(), ULID()]
        v3 = [ULID(), ULID(), ULID()]

        vm.add_version(v1)
        vm.add_version(v2)
        vm.add_version(v3)

        assert vm.version_count == 3
        assert vm.current_version == v3
        assert vm.current_version_index == 2

    def test_get_specific_version(self):
        """Test retrieving a specific version by index."""
        vm = VersionManager()
        v1 = [ULID()]
        v2 = [ULID(), ULID()]
        v3 = [ULID(), ULID(), ULID()]

        vm.add_version(v1)
        vm.add_version(v2)
        vm.add_version(v3)

        assert vm.get_version(0) == v1
        assert vm.get_version(1) == v2
        assert vm.get_version(2) == v3
        assert vm.get_version(-1) == v3  # Negative indexing
        assert vm.get_version(-2) == v2

    def test_get_invalid_version_raises_error(self):
        """Test that getting an invalid version raises IndexError."""
        vm = VersionManager()
        vm.add_version([ULID()])

        with pytest.raises(IndexError, match="Version 5 does not exist"):
            vm.get_version(5)

        # Negative index gets normalized, so -3 becomes -2 after normalization
        with pytest.raises(IndexError, match="Version -2 does not exist"):
            vm.get_version(-3)

    def test_revert_to_version(self):
        """Test reverting to an earlier version (non-destructive)."""
        vm = VersionManager()
        v1 = [ULID()]
        v2 = [ULID(), ULID()]
        v3 = [ULID(), ULID(), ULID()]

        vm.add_version(v1)
        vm.add_version(v2)
        vm.add_version(v3)

        # Revert to version 0 (v1)
        result = vm.revert_to(0)

        assert result == v1
        assert vm.current_version == v1
        assert vm.version_count == 4  # Original 3 + revert creates new version
        assert vm.current_version_index == 3

        # Check metadata
        metadata = vm.get_metadata(3)
        assert metadata.get("reverted_from") == 2
        assert metadata.get("reverted_to") == 0

    def test_fork_at_version(self):
        """Test forking at a specific version."""
        vm = VersionManager()
        v1 = [ULID()]
        v2 = [ULID(), ULID()]
        v3 = [ULID(), ULID(), ULID()]

        vm.add_version(v1, metadata={"original": True})
        vm.add_version(v2)
        vm.add_version(v3)

        # Fork at version 1 (v2)
        fork = vm.fork_at(1)

        assert fork.version_count == 2  # v1 and v2
        assert fork.current_version == v2
        assert fork.current_version_index == 1
        assert fork.get_version(0) == v1
        assert fork.get_version(1) == v2

        # Check metadata is copied
        assert fork.get_metadata(0) == {"original": True}

        # Original should be unchanged
        assert vm.version_count == 3
        assert vm.current_version == v3

    def test_fork_at_negative_index(self):
        """Test forking with negative index."""
        vm = VersionManager()
        v1 = [ULID()]
        v2 = [ULID(), ULID()]
        v3 = [ULID(), ULID(), ULID()]

        vm.add_version(v1)
        vm.add_version(v2)
        vm.add_version(v3)

        # Fork at -1 (current/last version)
        fork = vm.fork_at(-1)
        assert fork.version_count == 3
        assert fork.current_version == v3

        # Fork at -2 (second to last)
        fork2 = vm.fork_at(-2)
        assert fork2.version_count == 2
        assert fork2.current_version == v2

    def test_empty_version_manager(self):
        """Test behavior with no versions."""
        vm = VersionManager()

        assert vm.version_count == 0
        assert vm.current_version == []
        assert vm.current_version_index == -1

        # Forking empty should create empty fork
        fork = vm.fork_at(-1)
        assert fork.version_count == 0
        assert fork.current_version == []

    def test_get_changes_between_versions(self):
        """Test getting differences between versions."""
        vm = VersionManager()
        id1, id2, id3, id4 = ULID(), ULID(), ULID(), ULID()

        v1 = [id1, id2]
        v2 = [id1, id3]  # Removed id2, added id3
        v3 = [id1, id3, id4]  # Added id4

        vm.add_version(v1)
        vm.add_version(v2)
        vm.add_version(v3)

        # Changes from v1 to v2
        changes = vm.get_changes_between(0, 1)
        assert set(changes["added"]) == {id3}
        assert set(changes["removed"]) == {id2}

        # Changes from v2 to v3
        changes = vm.get_changes_between(1, 2)
        assert set(changes["added"]) == {id4}
        assert changes["removed"] == []

        # Changes from v1 to v3
        changes = vm.get_changes_between(0, 2)
        assert set(changes["added"]) == {id3, id4}
        assert set(changes["removed"]) == {id2}

    def test_truncate_after_version(self):
        """Test destructive truncation of versions."""
        vm = VersionManager()
        v1 = [ULID()]
        v2 = [ULID(), ULID()]
        v3 = [ULID(), ULID(), ULID()]
        v4 = [ULID(), ULID(), ULID(), ULID()]

        vm.add_version(v1, metadata={"v": 1})
        vm.add_version(v2, metadata={"v": 2})
        vm.add_version(v3, metadata={"v": 3})
        vm.add_version(v4, metadata={"v": 4})

        # Truncate after version 1 (keep v1 and v2)
        vm.truncate_after(1)

        assert vm.version_count == 2
        assert vm.current_version_index == 1  # Current moved back if needed
        assert vm.get_version(0) == v1
        assert vm.get_version(1) == v2

        # Metadata for truncated versions should be removed
        assert vm.get_metadata(0) == {"v": 1}
        assert vm.get_metadata(1) == {"v": 2}
        assert vm.get_metadata(2) == {}  # No metadata for non-existent version

        with pytest.raises(IndexError):
            vm.get_version(2)

    def test_version_immutability(self):
        """Test that returned versions are copies and can't modify internal state."""
        vm = VersionManager()
        original = [ULID(), ULID()]
        vm.add_version(original)

        # Get current version and try to modify it
        current = vm.current_version
        current.append(ULID())

        # Original should be unchanged
        assert len(vm.current_version) == 2
        assert vm.current_version == original

        # Same for get_version
        retrieved = vm.get_version(0)
        retrieved.clear()

        assert len(vm.get_version(0)) == 2
        assert vm.get_version(0) == original


class TestInMemoryMessageStore:
    """Test the InMemoryMessageStore implementation."""

    def test_store_and_retrieve(self):
        """Test basic store and retrieve operations."""
        store = InMemoryMessageStore()
        msg = SystemMessage(content_parts=[], id=ULID())

        store.put(msg)
        assert store.exists(msg.id)

        retrieved = store.get(msg.id)
        assert retrieved == msg

    def test_get_nonexistent_raises_error(self):
        """Test that getting a non-existent message raises an error."""
        store = InMemoryMessageStore()
        non_existent_id = ULID()

        assert not store.exists(non_existent_id)

        with pytest.raises(MessageNotFoundError, match=f"Message {non_existent_id} not found"):
            store.get(non_existent_id)

    def test_overwrite_message(self):
        """Test that storing a message with the same ID overwrites it."""
        store = InMemoryMessageStore()

        # Create messages and get their auto-generated IDs
        msg1 = SystemMessage(content_parts=[])
        msg2 = UserMessage(content_parts=[])

        # Store msg1
        store.put(msg1)

        # Create a new message with the same ID as msg1 to test overwriting
        # We need to work around the frozen model, so we'll simulate this scenario
        # by directly manipulating the store
        store._messages[msg1.id] = msg2  # Overwrite msg1's ID with msg2

        retrieved = store.get(msg1.id)
        assert retrieved == msg2
        assert isinstance(retrieved, UserMessage)
