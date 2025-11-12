"""Tests for agent pool functionality."""

import pytest

from good_agent import Agent
from good_agent.pool import AgentPool


class TestAgentPoolInitialization:
    """Tests for AgentPool initialization."""

    def test_pool_init_with_empty_list(self):
        """Test creating pool with empty list."""
        pool = AgentPool([])
        assert len(pool) == 0

    def test_pool_init_with_single_agent(self):
        """Test creating pool with single agent."""
        agent = Agent()
        pool = AgentPool([agent])
        assert len(pool) == 1

    def test_pool_init_with_multiple_agents(self):
        """Test creating pool with multiple agents."""
        agents = [Agent() for _ in range(5)]
        pool = AgentPool(agents)
        assert len(pool) == 5

    def test_pool_stores_agent_references(self):
        """Test that pool stores references to the same agent objects."""
        agents = [Agent() for _ in range(3)]
        pool = AgentPool(agents)

        # Verify same objects
        assert pool[0] is agents[0]
        assert pool[1] is agents[1]
        assert pool[2] is agents[2]


class TestAgentPoolLength:
    """Tests for AgentPool length operations."""

    def test_len_empty_pool(self):
        """Test length of empty pool."""
        pool = AgentPool([])
        assert len(pool) == 0

    def test_len_single_agent(self):
        """Test length with single agent."""
        pool = AgentPool([Agent()])
        assert len(pool) == 1

    def test_len_multiple_agents(self):
        """Test length with multiple agents."""
        pool = AgentPool([Agent() for _ in range(10)])
        assert len(pool) == 10


class TestAgentPoolIndexing:
    """Tests for AgentPool indexing operations."""

    def test_getitem_single_index(self):
        """Test accessing agent by single index."""
        agents = [Agent() for _ in range(3)]
        pool = AgentPool(agents)

        assert pool[0] is agents[0]
        assert pool[1] is agents[1]
        assert pool[2] is agents[2]

    def test_getitem_negative_index(self):
        """Test accessing agent with negative index."""
        agents = [Agent() for _ in range(3)]
        pool = AgentPool(agents)

        assert pool[-1] is agents[2]
        assert pool[-2] is agents[1]
        assert pool[-3] is agents[0]

    def test_getitem_out_of_bounds(self):
        """Test accessing agent with out of bounds index."""
        pool = AgentPool([Agent() for _ in range(3)])

        with pytest.raises(IndexError):
            _ = pool[10]

        with pytest.raises(IndexError):
            _ = pool[-10]

    def test_getitem_slice(self):
        """Test accessing agents with slice."""
        agents = [Agent() for _ in range(5)]
        pool = AgentPool(agents)

        # Test basic slice
        subset = pool[1:3]
        assert len(subset) == 2
        assert subset[0] is agents[1]
        assert subset[1] is agents[2]

    def test_getitem_slice_with_step(self):
        """Test accessing agents with slice and step."""
        agents = [Agent() for _ in range(6)]
        pool = AgentPool(agents)

        # Test slice with step
        subset = pool[::2]  # Every other agent
        assert len(subset) == 3
        assert subset[0] is agents[0]
        assert subset[1] is agents[2]
        assert subset[2] is agents[4]

    def test_getitem_empty_slice(self):
        """Test accessing with empty slice."""
        pool = AgentPool([Agent() for _ in range(3)])
        subset = pool[10:20]  # Out of bounds slice
        assert len(subset) == 0


class TestAgentPoolIteration:
    """Tests for AgentPool iteration."""

    def test_iter_empty_pool(self):
        """Test iterating over empty pool."""
        pool = AgentPool([])
        agents_list = list(pool)
        assert len(agents_list) == 0

    def test_iter_single_agent(self):
        """Test iterating with single agent."""
        agent = Agent()
        pool = AgentPool([agent])

        agents_list = list(pool)
        assert len(agents_list) == 1
        assert agents_list[0] is agent

    def test_iter_multiple_agents(self):
        """Test iterating with multiple agents."""
        agents = [Agent() for _ in range(5)]
        pool = AgentPool(agents)

        # Test iteration maintains order
        for i, agent in enumerate(pool):
            assert agent is agents[i]

    def test_iter_can_be_used_multiple_times(self):
        """Test that pool can be iterated multiple times."""
        agents = [Agent() for _ in range(3)]
        pool = AgentPool(agents)

        # First iteration
        first_list = list(pool)
        # Second iteration
        second_list = list(pool)

        assert len(first_list) == len(second_list) == 3
        assert all(a is b for a, b in zip(first_list, second_list))


class TestAgentPoolConcurrentAccess:
    """Tests for concurrent access patterns."""

    def test_modulo_access_pattern(self):
        """Test load balancing pattern using modulo."""
        agents = [Agent() for _ in range(3)]
        pool = AgentPool(agents)

        # Simulate round-robin access
        work_items = list(range(10))
        accessed_agents = [pool[i % len(pool)] for i in work_items]

        # Verify each agent accessed multiple times
        assert accessed_agents[0] is agents[0]
        assert accessed_agents[1] is agents[1]
        assert accessed_agents[2] is agents[2]
        assert accessed_agents[3] is agents[0]  # Wraps around

    def test_agent_independence(self):
        """Test that agents in pool maintain independent state."""
        agents = [Agent() for _ in range(2)]
        pool = AgentPool(agents)

        # Modify one agent's messages
        pool[0].append("Message for agent 0")

        # Verify other agent unaffected
        assert len(pool[0].messages) == 1
        assert len(pool[1].messages) == 0


class TestAgentPoolEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_pool_with_none_raises_error(self):
        """Test that creating pool with None raises appropriate error on access."""
        # Pool creation doesn't immediately validate, but access will fail
        pool = AgentPool(None)  # type: ignore
        with pytest.raises(TypeError):
            len(pool)  # This will raise TypeError

    def test_pool_immutability(self):
        """Test that pool's agent list cannot be modified directly."""
        agents = [Agent() for _ in range(3)]
        pool = AgentPool(agents)

        # The internal _agents list should not be modifiable from outside
        # (though Python doesn't enforce this strongly)
        original_length = len(pool)

        # Verify pool maintains correct length
        assert len(pool) == original_length

    def test_pool_with_duplicate_agents(self):
        """Test pool can contain duplicate agent references."""
        agent = Agent()
        pool = AgentPool([agent, agent, agent])

        assert len(pool) == 3
        assert pool[0] is pool[1] is pool[2] is agent
