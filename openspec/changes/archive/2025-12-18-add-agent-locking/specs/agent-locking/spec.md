# Agent Locking

## ADDED Requirements

### Requirement: Serialize Agent state mutations
The system SHALL provide a per-Agent async lock (or equivalent single-flight guard) that serializes stateful operations including `call`, `execute`, message append/replace, mode transitions, and version updates.

#### Scenario: Overlapping execute calls serialize
- **GIVEN** two coroutines invoke `agent.execute()` concurrently on the same Agent
- **WHEN** both attempts would mutate messages or mode state
- **THEN** one SHALL wait for the lock while the other holds it, preventing interleaved message/version updates.

### Requirement: Preserve tool parallelism while serializing emissions
Tool execution MAY remain parallel, but all Agent-affecting side effects from tools (assistant/tool message creation, pending-call tracking, TOOL_* event emissions that mutate state) SHALL pass through the Agent lock to maintain deterministic ordering.

#### Scenario: Parallel tool execution with ordered emissions
- **GIVEN** `invoke_many` runs multiple tools in parallel
- **WHEN** their results are emitted as messages
- **THEN** emission/order SHALL be serialized under the Agent lock so `ToolMessage` entries reflect the corresponding `tool_call_id` order without interleaving from other Agent operations.

### Requirement: Thread-safe proxy for cross-thread calls
The system SHALL expose a documented entry surface (e.g., proxy or helper) that allows callers on other threads to schedule Agent operations onto its event loop while respecting the Agent lock.

#### Scenario: Cross-thread call uses proxy safely
- **GIVEN** a caller in a different thread wants to invoke `agent.call()`
- **WHEN** they use the provided proxy/helper
- **THEN** the work SHALL be scheduled onto the Agent’s loop and acquire the Agent lock, preventing races with in-loop operations.

### Requirement: Guarded mutation utilities for handlers
Handlers and components that mutate Agent state SHALL have a supported way to execute under the Agent lock (or be explicitly prevented), so fire-and-forget `do()` handlers cannot corrupt state by concurrent mutation.

#### Scenario: Mutating event handler runs under guard
- **GIVEN** an event handler triggered via `do()` needs to append a message
- **WHEN** it uses the provided guarded mutation helper/context
- **THEN** the append SHALL acquire the Agent lock, avoiding concurrent mutation with other Agent operations.
