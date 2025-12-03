from collections.abc import Iterator
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from good_agent.agent.core import Agent


class AgentPool:
    """Immutable collection of pre-initialized Agents for fan-out workloads.

    This is a read-only container. It does not manage locks or concurrency for
    the contained agents. The caller must ensure that concurrent tasks utilize
    distinct agent instances.

    Access is index-based and thread-safe for reads; see
    ``examples/pool/agent_pool.py`` for round-robin dispatching.
    """

    def __init__(self, agents: list[Agent]):
        """Store agents without copying; the pool itself remains read-only."""
        self._agents = agents

    def __len__(self) -> int:
        """Get the number of agents in the pool"""
        return len(self._agents)

    def __iter__(self) -> Iterator[Agent]:
        """Iterate over agents in the pool"""
        return iter(self._agents)

    @overload
    def __getitem__(self, index: int) -> Agent: ...

    @overload
    def __getitem__(self, index: slice) -> list[Agent]: ...

    def __getitem__(self, index: int | slice) -> Agent | list[Agent]:
        """
        Get agent(s) by index.

        Args:
            index: Integer index or slice

        Returns:
            Single agent or list of agents
        """
        return self._agents[index]
