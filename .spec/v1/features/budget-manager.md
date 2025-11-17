# BudgetManager Feature Specification

## Overview
The BudgetManager is an `AgentComponent` that tracks and enforces resource consumption limits for agentic operations. It generalizes beyond cost tracking to support **any finite resource**: API costs, token usage, time budgets, context window consumption, rate limits, or custom metrics.

**Key architectural touchpoints:**
- Extends `AgentComponent` for lifecycle integration and tool registration
- Hooks into existing `AgentEvents` (LLM calls, tool execution, iteration tracking)
- Supports single-agent and multi-agent session budgets (shared component pattern)
- Provides storage abstraction for persistent budget tracking across invocations
- Implements configurable policies (blocking, warnings, agent context injection)

---

## Requirements & Constraints

### Async-First
- All budget tracking methods are `async` to support async event handlers
- Storage backends must be async-compatible
- Policy enforcement respects event loop semantics

### Python-Native Ergonomics
- Use `@on` decorator for event handler registration
- Component tools via `@tool` decorator for budget inspection/reset
- Context managers for temporary budget overrides (`async with budget.override(...)`)
- Type-safe resource definitions via Pydantic models

### Composability
- Must work with existing `AgentComponent` dependency injection
- Compatible with agent piping (`agent_a | agent_b`) for shared session budgets
- Allows multiple budget types per agent via subclassing

### Testing Integration
- Budget state should be capturable in transcript recordings
- Mocking interfaces for storage backends and policy handlers

---

## Architecture Hooks

### Event Integration
Hooks into existing `AgentEvents`:
- **`LLM_COMPLETE_AFTER`** / **`LLM_EXTRACT_AFTER`**: Track token usage and API costs
- **`LLM_STREAM_CHUNK`**: Accumulate streaming token counts
- **`TOOL_CALL_AFTER`**: Track tool execution costs (if applicable)
- **`EXECUTE_ITERATION_AFTER`**: Track time/iteration budgets
- **`AGENT_INIT_AFTER`**: Load persisted budget state
- New events may be added: **`BUDGET_THRESHOLD_WARNING`**, **`BUDGET_EXHAUSTED`**

### Component Lifecycle
- **`setup(agent)`**: Register event handlers early
- **`install(agent)`**: Initialize storage backend, load state, register tools
- **`close()`**: Persist final budget state

### Storage Abstraction
Interface for persistence across invocations:
- In-memory (ephemeral, single call)
- File-based (JSON/YAML, local development)
- Redis/LMDB (fast KV stores, session-based)
- PostgreSQL (relational, audit trails)

---

## API Sketches

### Basic Usage: Cost Budget

```python
from good_agent import Agent
from good_agent.budgets import CostBudgetManager

# Single-agent cost tracking
budget = CostBudgetManager(
    max_cost_usd=5.0,
    policy='warn_and_block',  # 'warn', 'block', 'warn_and_block', 'inject_context'
    warning_thresholds=[0.5, 0.8, 0.9],  # Percentages
    storage='memory',  # 'memory', 'file:./budgets.json', 'redis://...', 'postgres://...'
)

async with Agent(
    "You are a helpful assistant.",
    extensions=[budget]
) as agent:
    agent.append("Explain quantum computing in detail.")
    await agent.call()

    # Budget automatically tracked via LLM_COMPLETE_AFTER event
    print(f"Cost so far: ${budget.consumed:.4f} / ${budget.limit:.2f}")
    print(f"Remaining: ${budget.remaining:.4f}")
```

### Multi-Agent Session Budget

```python
# Shared budget across multiple agents
session_budget = CostBudgetManager(
    max_cost_usd=10.0,
    session_id='research-session-42',
    storage='redis://localhost:6379',
    policy='inject_context',  # Warn agent in system context
)

researcher = Agent("Research assistant", extensions=[session_budget])
writer = Agent("Technical writer", extensions=[session_budget])

async with (researcher | writer) as conversation:
    # Both agents share the same budget tracker
    # Budget persists across multiple invocations via session_id
    researcher.append("Research latest AI trends")
    await conversation.execute()
```

### Context Window Budget

```python
from good_agent.budgets import ContextWindowBudgetManager

context_budget = ContextWindowBudgetManager(
    max_tokens=8192,
    policy='inject_context',
    warning_thresholds=[0.7, 0.9],
)

async with Agent("Assistant", extensions=[context_budget]) as agent:
    # Budget tracks cumulative context usage
    for i in range(10):
        agent.append(f"Task {i}: Analyze document...")
        await agent.call()

        # Agent receives injected warnings like:
        # "[SYSTEM NOTICE] Context budget: 7340/8192 tokens (90% used). Consider summarizing."
```

### Time Budget

```python
from good_agent.budgets import TimeBudgetManager
from datetime import timedelta

time_budget = TimeBudgetManager(
    max_duration=timedelta(minutes=5),
    policy='block',
)

async with Agent("Assistant", extensions=[time_budget]) as agent:
    agent.append("Complex long-running task...")
    try:
        await agent.call()
    except BudgetExhaustedError as e:
        print(f"Time limit exceeded: {e.consumed} / {e.limit}")
```

### Custom Resource Budget

```python
from good_agent.budgets import BudgetManager, BudgetResource
from pydantic import BaseModel

class ApiCallResource(BudgetResource):
    """Track number of API calls."""

    def measure(self, event: str, ctx: EventContext) -> float:
        # Increment by 1 for each LLM call
        if event in [AgentEvents.LLM_COMPLETE_AFTER, AgentEvents.LLM_EXTRACT_AFTER]:
            return 1.0
        return 0.0

    def format_amount(self, amount: float) -> str:
        return f"{int(amount)} calls"

api_budget = BudgetManager(
    resource=ApiCallResource(),
    limit=50,
    policy='warn_and_block',
)
```

### Multiple Budgets Per Agent

```python
# Use subclassing to register multiple budget types
class MyCostBudget(CostBudgetManager):
    pass

class MyTimeBudget(TimeBudgetManager):
    pass

async with Agent(
    "Assistant",
    extensions=[
        MyCostBudget(max_cost_usd=5.0),
        MyTimeBudget(max_duration=timedelta(minutes=3)),
    ]
) as agent:
    # Both budgets active simultaneously
    agent.append("Task...")
    await agent.call()
```

### Budget Tools (Agent-Accessible)

```python
# Agents can query their own budgets via tools
budget = CostBudgetManager(max_cost_usd=10.0, expose_tools=True)

async with Agent("Assistant", extensions=[budget]) as agent:
    # Agent can call: check_budget, reset_budget (if allowed)
    agent.append("How much of my budget have I used?")
    await agent.call()
    # Agent uses tool: check_budget() -> "Consumed: $3.45 / $10.00 (34.5%)"
```

---

## Core Interface Design

### BudgetResource (Abstract Base)

```python
from abc import ABC, abstractmethod
from typing import Any
from good_agent.events import AgentEvents, EventContext

class BudgetResource(ABC):
    """Abstract resource type for budget tracking."""

    @abstractmethod
    def measure(self, event: str, ctx: EventContext) -> float:
        """Extract resource consumption from an event context."""
        pass

    @abstractmethod
    def format_amount(self, amount: float) -> str:
        """Human-readable formatting of consumed amount."""
        pass

    @property
    @abstractmethod
    def unit(self) -> str:
        """Resource unit name (e.g., 'USD', 'tokens', 'seconds')."""
        pass
```

### Concrete Resource Implementations

```python
class CostResource(BudgetResource):
    """Tracks API call costs in USD."""

    def measure(self, event: str, ctx: EventContext) -> float:
        if event == AgentEvents.LLM_COMPLETE_AFTER:
            usage = ctx.parameters.get('usage', {})
            # Calculate cost from usage (model-specific pricing)
            return self._calculate_cost(usage, ctx.parameters.get('model'))
        return 0.0

    def format_amount(self, amount: float) -> str:
        return f"${amount:.4f}"

    @property
    def unit(self) -> str:
        return "USD"

class TokenResource(BudgetResource):
    """Tracks cumulative token usage."""

    def measure(self, event: str, ctx: EventContext) -> float:
        if event in [AgentEvents.LLM_COMPLETE_AFTER, AgentEvents.LLM_EXTRACT_AFTER]:
            usage = ctx.parameters.get('usage', {})
            return usage.get('total_tokens', 0)
        elif event == AgentEvents.LLM_STREAM_CHUNK:
            # Accumulate streaming tokens
            chunk = ctx.parameters.get('chunk', {})
            return chunk.get('usage', {}).get('total_tokens', 0)
        return 0.0

    def format_amount(self, amount: float) -> str:
        return f"{int(amount)} tokens"

    @property
    def unit(self) -> str:
        return "tokens"

class TimeResource(BudgetResource):
    """Tracks elapsed time."""

    def __init__(self):
        self._start_time = None

    def measure(self, event: str, ctx: EventContext) -> float:
        if event == AgentEvents.EXECUTE_BEFORE:
            self._start_time = time.time()
            return 0.0
        elif event == AgentEvents.EXECUTE_ITERATION_AFTER:
            if self._start_time:
                return time.time() - self._start_time
        return 0.0

    def format_amount(self, amount: float) -> str:
        return f"{amount:.2f}s"

    @property
    def unit(self) -> str:
        return "seconds"
```

### BudgetPolicy (Behavioral Abstraction)

```python
from enum import Enum
from typing import Protocol

class BudgetPolicyAction(Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    INJECT_CONTEXT = "inject_context"

class BudgetPolicy(Protocol):
    """Defines behavior when budget thresholds are reached."""

    async def on_threshold(
        self,
        agent: Agent,
        consumed: float,
        limit: float,
        threshold_pct: float,
        resource: BudgetResource,
    ) -> BudgetPolicyAction:
        """Called when a warning threshold is crossed."""
        ...

    async def on_exhausted(
        self,
        agent: Agent,
        consumed: float,
        limit: float,
        resource: BudgetResource,
    ) -> BudgetPolicyAction:
        """Called when budget is fully consumed."""
        ...

# Built-in policies
class WarnPolicy(BudgetPolicy):
    async def on_threshold(self, agent, consumed, limit, threshold_pct, resource):
        logger.warning(f"Budget {threshold_pct*100}% consumed: {consumed}/{limit} {resource.unit}")
        return BudgetPolicyAction.ALLOW

    async def on_exhausted(self, agent, consumed, limit, resource):
        logger.error(f"Budget exhausted: {consumed}/{limit} {resource.unit}")
        return BudgetPolicyAction.ALLOW  # Allow but warn

class BlockPolicy(BudgetPolicy):
    async def on_exhausted(self, agent, consumed, limit, resource):
        raise BudgetExhaustedError(f"Budget exceeded: {consumed}/{limit} {resource.unit}")

class InjectContextPolicy(BudgetPolicy):
    async def on_threshold(self, agent, consumed, limit, threshold_pct, resource):
        warning = f"[SYSTEM NOTICE] Budget: {consumed}/{limit} {resource.unit} ({threshold_pct*100:.0f}% used)"
        agent.append(warning, role='system')
        return BudgetPolicyAction.INJECT_CONTEXT
```

### Storage Interface

```python
class BudgetStorage(Protocol):
    """Persistence layer for budget state."""

    async def save(self, session_id: str, state: BudgetState) -> None:
        """Persist budget state."""
        ...

    async def load(self, session_id: str) -> BudgetState | None:
        """Retrieve budget state."""
        ...

    async def delete(self, session_id: str) -> None:
        """Remove budget state."""
        ...

@dataclass
class BudgetState:
    """Serializable budget state."""
    consumed: float
    limit: float
    resource_type: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

# Implementations
class MemoryStorage(BudgetStorage):
    """Ephemeral in-memory storage (single invocation)."""
    ...

class FileStorage(BudgetStorage):
    """JSON/YAML file storage."""
    def __init__(self, file_path: Path):
        self.file_path = file_path

class RedisStorage(BudgetStorage):
    """Redis-backed storage for distributed sessions."""
    def __init__(self, redis_url: str):
        self.redis_url = redis_url

class PostgresStorage(BudgetStorage):
    """PostgreSQL storage with audit trails."""
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
```

### BudgetManager Component

```python
from good_agent import AgentComponent, tool
from good_agent.events import AgentEvents
from good_agent.core.event_router import EventContext, on

class BudgetManager(AgentComponent):
    """Core budget tracking component."""

    def __init__(
        self,
        resource: BudgetResource,
        limit: float,
        policy: BudgetPolicy | str = 'warn',
        warning_thresholds: list[float] = None,
        session_id: str | None = None,
        storage: BudgetStorage | str = 'memory',
        expose_tools: bool = False,
    ):
        super().__init__()
        self.resource = resource
        self.limit = limit
        self.policy = self._resolve_policy(policy)
        self.warning_thresholds = sorted(warning_thresholds or [0.8, 0.9])
        self.session_id = session_id or f"budget-{uuid.uuid4()}"
        self.storage = self._resolve_storage(storage)
        self.expose_tools = expose_tools

        self._consumed = 0.0
        self._triggered_thresholds: set[float] = set()

    async def install(self, agent: Agent):
        await super().install(agent)
        # Load persisted state
        if state := await self.storage.load(self.session_id):
            self._consumed = state.consumed

    @on(AgentEvents.LLM_COMPLETE_AFTER, priority=150)
    @on(AgentEvents.LLM_EXTRACT_AFTER, priority=150)
    @on(AgentEvents.LLM_STREAM_CHUNK, priority=150)
    @on(AgentEvents.EXECUTE_ITERATION_AFTER, priority=150)
    async def _track_consumption(self, ctx: EventContext):
        """Track resource consumption from events."""
        if not self.enabled:
            return

        amount = self.resource.measure(ctx.event, ctx)
        if amount > 0:
            self._consumed += amount
            await self._check_thresholds()
            await self._persist_state()

    async def _check_thresholds(self):
        """Check and enforce budget policies."""
        pct = self._consumed / self.limit

        # Check warning thresholds
        for threshold in self.warning_thresholds:
            if pct >= threshold and threshold not in self._triggered_thresholds:
                self._triggered_thresholds.add(threshold)
                action = await self.policy.on_threshold(
                    self.agent, self._consumed, self.limit, threshold, self.resource
                )
                if action == BudgetPolicyAction.BLOCK:
                    raise BudgetExhaustedError(f"Budget threshold exceeded at {threshold*100}%")

        # Check exhaustion
        if self._consumed >= self.limit:
            action = await self.policy.on_exhausted(
                self.agent, self._consumed, self.limit, self.resource
            )
            if action == BudgetPolicyAction.BLOCK:
                raise BudgetExhaustedError(f"Budget exhausted: {self._consumed}/{self.limit}")

    async def _persist_state(self):
        """Save current budget state."""
        state = BudgetState(
            consumed=self._consumed,
            limit=self.limit,
            resource_type=self.resource.__class__.__name__,
            session_id=self.session_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await self.storage.save(self.session_id, state)

    @tool
    def check_budget(self) -> str:
        """Check current budget status."""
        pct = (self._consumed / self.limit) * 100
        return (
            f"Budget Status:\n"
            f"Consumed: {self.resource.format_amount(self._consumed)}\n"
            f"Limit: {self.resource.format_amount(self.limit)}\n"
            f"Used: {pct:.1f}%\n"
            f"Remaining: {self.resource.format_amount(self.limit - self._consumed)}"
        )

    @tool
    async def reset_budget(self, confirm: bool = False) -> str:
        """Reset budget consumption (requires confirmation)."""
        if not confirm:
            return "Reset requires confirmation. Call with confirm=True."
        self._consumed = 0.0
        self._triggered_thresholds.clear()
        await self._persist_state()
        return f"Budget reset. Limit: {self.resource.format_amount(self.limit)}"

    @property
    def consumed(self) -> float:
        return self._consumed

    @property
    def remaining(self) -> float:
        return max(0, self.limit - self._consumed)

    @property
    def percentage_used(self) -> float:
        return (self._consumed / self.limit) * 100

# Convenience subclasses
class CostBudgetManager(BudgetManager):
    def __init__(self, max_cost_usd: float, **kwargs):
        super().__init__(resource=CostResource(), limit=max_cost_usd, **kwargs)

class TokenBudgetManager(BudgetManager):
    def __init__(self, max_tokens: int, **kwargs):
        super().__init__(resource=TokenResource(), limit=float(max_tokens), **kwargs)

class TimeBudgetManager(BudgetManager):
    def __init__(self, max_duration: timedelta, **kwargs):
        super().__init__(resource=TimeResource(), limit=max_duration.total_seconds(), **kwargs)

class ContextWindowBudgetManager(BudgetManager):
    """Tracks context window usage (cumulative tokens in history)."""
    def __init__(self, max_tokens: int, **kwargs):
        super().__init__(resource=ContextWindowResource(), limit=float(max_tokens), **kwargs)
```

---

## Lifecycle & State

### Initialization Flow
1. Component instantiated with config (limit, policy, storage)
2. `setup(agent)`: Register event handlers via `@on` decorators
3. `install(agent)`: Load persisted state from storage, register tools
4. Ready to track events

### Event Processing
1. Relevant event fires (e.g., `LLM_COMPLETE_AFTER`)
2. `_track_consumption` handler invoked with high priority (150)
3. Resource extracts consumption amount from `EventContext`
4. Cumulative `_consumed` updated
5. Thresholds checked, policies enforced
6. State persisted to storage

### Shutdown
1. `close()` called (or context manager exit)
2. Final state persisted to storage
3. Resources cleaned up

### Multi-Agent Sessions
- Single `BudgetManager` instance shared across agents (via `extensions=[shared_budget]`)
- `session_id` ties budget to a conversation/workflow
- Storage backend ensures state consistency across agents

---

## Testing Strategy

### Unit Tests
- Mock `BudgetResource.measure()` to return predictable values
- Test threshold triggering and policy enforcement
- Validate storage save/load roundtrips

### Integration Tests
- Test with actual `Agent` execution and LLM calls (using transcripts)
- Verify budget tracking across multi-agent pipes
- Test persistence across separate `async with Agent(...)` invocations

### Transcript Compatibility
- Budget state should be capturable in transcript metadata
- Replay should restore budget state for deterministic testing

### Fixtures
```python
@pytest.fixture
def mock_budget():
    return BudgetManager(
        resource=MockResource(),
        limit=100.0,
        storage='memory',
    )

@pytest.fixture
def mock_storage():
    return MemoryStorage()
```

---

## Open Questions / TODOs

1. **Context window tracking**: Should we measure just the current history snapshot or cumulative tokens across all calls? The latter matches "context as budget" better but requires careful design.

2. **Rate limiting**: Is a separate `RateLimitBudgetManager` needed, or can `TimeBudgetManager` cover this with per-interval resets?

3. **Budget inheritance**: Should forked agents inherit parent budget state, or get fresh budgets?

4. **Policy composition**: Allow stacking multiple policies (e.g., warn + inject context)?

5. **Budget rollover**: Support for unused budget carrying over between sessions?

6. **Audit trails**: Should storage backends automatically log all budget changes for compliance/debugging?

7. **Dynamic limits**: Support for adjusting `limit` mid-session based on external factors?

8. **Budget pooling**: Multiple agents drawing from a shared pool with sub-limits per agent?

---

## Implementation Phases

### Phase 1: Core Infrastructure (MVP)
- `BudgetResource` abstraction
- `BudgetManager` component with event tracking
- `CostResource` and `TokenResource` implementations
- `MemoryStorage` backend
- Basic `WarnPolicy` and `BlockPolicy`

### Phase 2: Advanced Resources
- `TimeResource` and `TimeBudgetManager`
- `ContextWindowResource` for context tracking
- Custom resource examples

### Phase 3: Persistence
- `FileStorage` backend
- `RedisStorage` backend
- Session ID management

### Phase 4: Advanced Policies
- `InjectContextPolicy` for agent-aware warnings
- Policy composition framework
- User-facing policy callbacks

### Phase 5: Multi-Agent Support
- Shared budget validation across piped agents
- Budget inheritance for forked agents
- Sub-budget allocation

### Phase 6: Observability & Tools
- Agent-accessible budget tools (`@tool` methods)
- Rich logging and telemetry integration
- Dashboard/metrics export

---

## Example: End-to-End Workflow

```python
from good_agent import Agent
from good_agent.budgets import CostBudgetManager, ContextWindowBudgetManager

# Research session with cost and context budgets
session_id = "research-2025-01-15"

cost_budget = CostBudgetManager(
    max_cost_usd=5.0,
    session_id=session_id,
    storage='redis://localhost:6379',
    policy='warn_and_block',
    warning_thresholds=[0.5, 0.8, 0.9],
)

context_budget = ContextWindowBudgetManager(
    max_tokens=100_000,
    session_id=session_id,
    storage='redis://localhost:6379',
    policy='inject_context',
)

# First invocation
async with Agent(
    "You are a research assistant.",
    extensions=[cost_budget, context_budget],
) as agent:
    agent.append("Research quantum computing trends in 2025.")
    await agent.call()
    print(f"Cost: ${cost_budget.consumed:.4f}")

# Later invocation (same session)
async with Agent(
    "You are a research assistant.",
    extensions=[cost_budget, context_budget],  # State restored from Redis
) as agent:
    agent.append("Summarize your previous research.")
    await agent.call()  # Budget continues from previous invocation
    print(f"Total session cost: ${cost_budget.consumed:.4f}")

# Multi-agent workflow
researcher = Agent("Researcher", extensions=[cost_budget])
writer = Agent("Writer", extensions=[cost_budget])

async with (researcher | writer) as conversation:
    researcher.append("Research AI safety")
    # Both agents share the same budget
    await conversation.execute()
```

---

## Summary

The BudgetManager provides a **flexible, extensible abstraction** for tracking and enforcing limits on any finite resource in agentic workflows:
- **Pythonic**: Uses `AgentComponent`, `@on` decorators, context managers, and type-safe Pydantic models
- **Composable**: Works with single agents, multi-agent pipes, and forked agents
- **Persistent**: Supports multiple storage backends for session-based tracking
- **Configurable**: Pluggable resources, policies, and storage adapters
- **Observable**: Exposes budget status via tools and telemetry

This design naturally extends to context windows by treating them as just another budget type—a finite resource that gets consumed with each LLM call.
