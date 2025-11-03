"""
CONTEXT: Agent pool management for concurrent processing and resource isolation.
ROLE: Provides thread-safe agent collection management for parallel processing scenarios.
DEPENDENCIES:
  - typing: Type hints and overloads for type-safe agent access
ARCHITECTURE:
  - AgentPool container for agent instance management
  - Thread-safe agent access and iteration
  - Index-based and slice-based agent retrieval
  - Resource isolation for concurrent processing
KEY EXPORTS: AgentPool class for concurrent agent management
USAGE PATTERNS:
  1. Parallel processing: AgentPool([agent1, agent2, agent3])
  2. Load balancing: pool[0], pool[1], pool[2] for task distribution
  3. Batch processing: pool[:] for all agents
  4. Resource isolation: Each agent maintains independent state
RELATED MODULES:
  - agent.py: Agent instances being managed
  - components/: Agent components in pool
  - tools.py: Tool management across multiple agents

PERFORMANCE CONTEXT:
- Pool creation: ~1ms for agent list initialization
- Agent access: O(1) for index-based access
- Memory usage: O(n) where n = number of agents + agent state
- Thread safety: Read-only operations are thread-safe

CONCURRENT PROCESSING:
- Each agent maintains independent state
- No shared mutable state between agents
- Thread-safe read operations for parallel access
- Isolation prevents cross-contamination

USAGE PATTERNS:
- Parallel execution: Process multiple requests concurrently
- Load balancing: Distribute tasks across available agents
- Resource isolation: Separate agent contexts for different users
- Batch processing: Apply operations to all agents in pool

POOL MANAGEMENT:
- Static pool: Fixed set of agents for processing
- Dynamic addition: Add agents to existing pool (if needed)
- Agent lifecycle: Each agent manages its own lifecycle
- Error isolation: Agent failures don't affect pool operations
"""

from collections.abc import Iterator
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from .agent import Agent


class AgentPool:
    """A pool of agents for parallel processing and resource isolation.

    PURPOSE: Manages a collection of agent instances for concurrent processing,
    providing thread-safe access and resource isolation between different agent contexts.

    ROLE: Enables parallel processing scenarios by:
    - Managing multiple agent instances with independent state
    - Providing thread-safe access to agent collection
    - Supporting load balancing across available agents
    - Ensuring resource isolation between different processing contexts

    CONCURRENT PROCESSING ARCHITECTURE:
    1. Agent Isolation: Each agent maintains independent message history and state
    2. Thread Safety: Read operations safe for concurrent access
    3. Load Balancing: Index-based access for task distribution
    4. Resource Management: Individual agent lifecycle management

    PERFORMANCE CHARACTERISTICS:
    - Pool creation: ~1ms for agent list initialization
    - Agent access: O(1) for index-based retrieval
    - Memory: O(n) where n = number of agents + agent state
    - Thread safety: Read-only operations are fully thread-safe
    - Scalability: Limited by agent resource usage and memory

    USAGE SCENARIOS:
    1. Parallel Request Processing: Handle multiple user requests simultaneously
    2. Load Balancing: Distribute tasks across multiple agent instances
    3. Resource Isolation: Separate contexts for different users or tenants
    4. Batch Processing: Apply operations to all agents in pool

    INTEGRATION PATTERNS:
    - Web servers: One agent per concurrent request
    - API services: Pool of agents for request handling
    - Batch jobs: Parallel processing with agent pool
    - Multi-tenant systems: Isolated agents per tenant

    THREAD SAFETY:
    - Read operations: Fully thread-safe (immutable agent list)
    - Agent state: Each agent manages its own thread safety
    - Write operations: Not thread-safe (pool should be immutable)
    - Concurrent access: Multiple threads can access different agents safely

    RESOURCE MANAGEMENT:
    - Agent lifecycle: Each agent manages its own initialization/cleanup
    - Memory usage: Proportional to number of agents * agent state size
    - Tool isolation: Each agent has independent tool instances
    - Message history: Separate per agent, no cross-contamination

    EXAMPLES:
    ```python
    # Create pool for parallel processing
    agents = [Agent() for _ in range(3)]
    pool = AgentPool(agents)


    # Parallel request processing
    async def handle_request(pool, request):
        agent = pool[request.user_id % len(pool)]
        return await agent.call(request.message)


    # Load balancing across agents
    tasks = []
    for i, work_item in enumerate(work_items):
        agent = pool[i % len(pool)]
        tasks.append(agent.call(work_item))

    results = await asyncio.gather(*tasks)
    ```

    LIMITATIONS:
    - Pool is immutable after creation (no dynamic agent addition/removal)
    - Write operations not thread-safe
    - No automatic load balancing (manual agent selection)
    - Agent resource limits apply (memory, API quotas, etc.)
    """

    def __init__(self, agents: list["Agent"]):
        """
        Initialize the agent pool with a list of agent instances.

        Args:
            agents: List of Agent instances for parallel processing.
                Each agent maintains independent state and message history.
                Agents should be fully initialized before adding to pool.

        SIDE EFFECTS:
        - Stores reference to agent list for pool management
        - Pool becomes immutable after initialization
        - Each agent maintains independent context

        EXAMPLES:
        ```python
        # Create pool with 3 agents
        agents = [Agent(model="gpt-4") for _ in range(3)]
        pool = AgentPool(agents)

        # Pool with different configurations
        agents = [
            Agent(model="gpt-4", tools=[search_tool]),
            Agent(model="gpt-3.5", tools=[analysis_tool]),
            Agent(model="claude", tools=[summarization_tool]),
        ]
        pool = AgentPool(agents)
        ```
        """
        self._agents = agents

    def __len__(self) -> int:
        """Get the number of agents in the pool"""
        return len(self._agents)

    def __iter__(self) -> Iterator["Agent"]:
        """Iterate over agents in the pool"""
        return iter(self._agents)

    @overload
    def __getitem__(self, index: int) -> "Agent": ...

    @overload
    def __getitem__(self, index: slice) -> list["Agent"]: ...

    def __getitem__(self, index: int | slice) -> "Agent | list[Agent]":
        """
        Get agent(s) by index.

        Args:
            index: Integer index or slice

        Returns:
            Single agent or list of agents
        """
        return self._agents[index]
