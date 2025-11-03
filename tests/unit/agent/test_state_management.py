import asyncio

import pytest
from good_agent import Agent
from good_agent.store import message_store


class TestStateManagement:
    """Test agent state management and versioning"""

    def test_session_id_initialization(self):
        """Test session ID behavior"""
        # Agent without messages uses agent ID as session ID
        agent = Agent()
        assert agent.session_id == agent.id

        # Session ID remains the same even with system prompt (consistent behavior)
        agent = Agent("System prompt")
        session_id = agent.session_id
        assert session_id == agent.id  # Session ID should be agent ID, not message ID

        # Session ID doesn't change with new messages
        agent.append("Hello")
        agent.append("World")
        assert agent.session_id == session_id

    def test_version_tracking(self):
        """Test version ID updates on state changes"""
        agent = Agent("System prompt")
        initial_version = agent.version_id

        # Version changes on append
        agent.append("User message")
        assert agent.version_id != initial_version

        # Each change creates new version
        second_version = agent.version_id
        agent.append("Another message")
        assert agent.version_id != second_version
        assert agent.version_id != initial_version

    def test_version_history(self):
        """Test version history tracking"""
        agent = Agent("System prompt")
        assert len(agent._versions) == 1
        assert agent._versions[0] == [agent.messages[0].id]

        # Add messages and check history
        agent.append("Message 1")
        assert len(agent._versions) == 2
        assert agent._versions[1] == [agent.messages[0].id, agent.messages[1].id]

        agent.append("Message 2")
        assert len(agent._versions) == 3
        assert len(agent._versions[2]) == 3  # All 3 messages

    @pytest.mark.asyncio
    async def test_system_message_versioning(self):
        """Test version updates when setting system message"""
        async with Agent() as agent:
            agent.append("User message")

            initial_version = agent.version_id
            agent.set_system_message("New system prompt")

            # Version should change
            assert agent.version_id != initial_version
            assert agent.messages[0].role == "system"
            assert agent.messages[0].content == "New system prompt"

    @pytest.mark.asyncio
    async def test_fork_basic(self):
        """Test basic agent forking"""
        async with Agent("System prompt") as original:
            original.append("Hello")
            original.append("World")

            # Fork the agent
            async with original.fork() as fork:
                # Different session, same version
                assert fork.session_id != original.session_id
                assert fork.version_id == original.version_id

                # Same number of messages
                assert len(fork.messages) == len(original.messages)

                # Messages have different IDs but same content
                for i, (orig_msg, fork_msg) in enumerate(
                    zip(original.messages, fork.messages, strict=False)
                ):
                    assert orig_msg.id != fork_msg.id
                    assert orig_msg.content == fork_msg.content
                    assert orig_msg.role == fork_msg.role

    @pytest.mark.asyncio
    async def test_fork_independence(self):
        """Test that forked agents are independent"""
        original = Agent("System prompt")
        original.append("Original message")

        fork = original.fork()

        # Modify fork
        fork.append("Fork message")

        # Original unchanged
        assert len(original.messages) == 2
        assert len(fork.messages) == 3
        assert original.version_id != fork.version_id

    def test_slice_forking(self):
        """Test forking with slice notation"""
        agent = Agent("System prompt")
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Fork with first 2 messages
        partial = agent[:2]

        from good_agent.agent import Agent as AgentClass

        assert isinstance(partial, AgentClass)
        assert len(partial.messages) == 2
        assert partial.messages[0].content == "System prompt"
        assert partial.messages[1].content == "Message 1"
        assert partial.session_id != agent.session_id

    def test_index_access(self):
        """Test accessing messages by index"""
        agent = Agent("System prompt")
        agent.append("Message 1")
        agent.append("Message 2")

        # Access by index returns message
        assert agent[0].content == "System prompt"
        assert agent[1].content == "Message 1"
        assert agent[-1].content == "Message 2"

    @pytest.mark.asyncio
    async def test_spawn_with_count(self):
        """Test spawning multiple agents"""
        async with Agent("System prompt") as base:
            base.append("Base message")

            # Spawn 3 agents
            pool = await base.spawn(n=3)

            assert len(pool) == 3

            # Use context manager for spawned agents
            async with pool[0] as agent1, pool[1] as agent2, pool[2] as agent3:
                spawned_agents = [agent1, agent2, agent3]
                for agent in spawned_agents:
                    assert agent.session_id != base.session_id
                    assert agent.version_id == base.version_id
                    assert len(agent.messages) == 2

    @pytest.mark.asyncio
    async def test_spawn_with_prompts(self):
        """Test spawning with specific prompts"""
        base = Agent("System prompt")

        prompts = ["Task 1", "Task 2", "Task 3"]
        pool = await base.spawn(prompts=prompts)

        assert len(pool) == 3
        for i, agent in enumerate(pool):
            assert agent.session_id != base.session_id
            # Each agent should have base messages + its prompt
            assert agent.messages[-1].content == prompts[i]

    def test_message_store_integration(self):
        """Test that messages are stored globally"""
        agent = Agent("System prompt")
        agent.append("Test message")

        # All messages should be in store
        for msg in agent.messages:
            stored = message_store.get(msg.id)
            assert stored is not None
            assert stored.content == msg.content

    @pytest.mark.asyncio
    async def test_fork_message_persistence(self):
        """Test that forked messages are stored"""
        original = Agent("System prompt")
        original.append("Message")

        fork = original.fork()

        # Fork messages should be in store with new IDs
        for msg in fork.messages:
            stored = message_store.get(msg.id)
            assert stored is not None
            assert stored.content == msg.content

    def test_message_agent_reference(self):
        """Test that messages maintain agent reference"""
        agent = Agent("System prompt")
        agent.append("Test")

        # Messages should reference their agent
        for i, msg in enumerate(agent.messages):
            assert msg.agent is agent
            assert msg.index == i

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test thread safety of operations"""
        async with Agent("System prompt") as agent:

            async def append_message(msg):
                agent.append(msg)

            # Concurrent appends
            await asyncio.gather(
                append_message("Message 1"),
                append_message("Message 2"),
                append_message("Message 3"),
            )

            # All messages should be present
            assert len(agent.messages) == 4  # System + 3 messages

            # Version history should track all changes
            assert len(agent._versions) == 4

    @pytest.mark.asyncio
    async def test_fork_with_config_override(self):
        """Test forking with configuration changes"""
        original = Agent("System prompt", model="gpt-4", temperature=0.7)

        # Fork with different config
        fork = original.fork(model="gpt-3.5-turbo", temperature=0.5)

        # Config should be updated
        assert fork.config.get("model") == "gpt-3.5-turbo"
        assert fork.config.get("temperature") == 0.5

        # Original config unchanged
        assert original.config.get("model") == "gpt-4"
        assert original.config.get("temperature") == 0.7
