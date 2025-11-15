# Spec: Multi-model Agent Strategy & Stateful Planning Documents

## 1. Overview
- Extend the async-first `Agent` API to support a single agent orchestrating multiple LLM backends in parallel for reasoning/writing, while centralizing shared tool calls and history management.
- Introduce a dedicated `PlanningDocument` stateful resource that fuses existing stateful documents with agent modes to enforce entry/exit rituals, scoped TODO extraction, and completion criteria across multi-session workflows.

## 2. Multi-Model Agent Strategy
### Goals
1. Allow an `Agent` to branch its reasoning across heterogeneous models (different providers, temperatures, reasoning configs) for the same task.
2. Keep tool invocation deterministic by routing actual tool calls through a primary "execution" model while still letting branches suggest tool usage.
3. Provide consensus reducers (majority, weighted voting, critic synthesis) to merge branch outputs into a single assistant reply.
4. Keep API surface idiomatic: async context managers, dataclasses, and type-safe configuration objects.

### API Sketch
```python
from good_agent.multi import (
    MultiModelStrategy,
    ModelVariant,
    ConsensusReducer,
    CriticReducer,
)

strategy = MultiModelStrategy(
    variants=[
        ModelVariant(name="o1-preview", role="planner", temperature=0.4,
                     reasoning={"effort": "high"}),
        ModelVariant(name="gpt-4o-mini", role="writer", temperature=0.9),
        ModelVariant(name="claude-3-5", role="critic", reasoning={"effort": "medium"}),
    ],
    reducer=CriticReducer(primary="planner", reviewer="critic", final="writer"),
    max_parallel=3,
    shared_history=True,
    tool_policy="centralized",
)

async with Agent("You are a release planner.", multi=strategy) as agent:
    agent.append("Draft a migration plan for feature X")
    response = await agent.call()
```
- `variants` reuse existing agent config fields (model, temperature, reasoning) plus optional metadata (`weight`, `purpose`).
- `MultiModelStrategy` exposes hooks: `before_branch(agent, variant)`, `after_branch(agent, variant, message)` for extensions/components.
- `tool_policy` options: `centralized` (default, only the orchestrator executes tools), `delegated` (branch-specific limited tool sets), `hybrid` (critic/tool-specific mapping).

### Execution Flow
1. `agent.call()` detects `multi` and spawns branch tasks (via `asyncio.TaskGroup`) using `agent.fork()` to preserve system prompt/context while swapping `language_model` per `ModelVariant`.
2. Branches perform reasoning/writing; tool call requests are captured as intent messages and queued to the orchestrator.
3. Orchestrator deduplicates tool intents, executes via selected policy, and injects tool responses back into branches.
4. Once branches finish, `strategy.reducer` receives `BranchResult`s (content, citations, confidence, tool summaries) and emits the final `AssistantMessage`.
5. Final consensus metadata (per-branch scores, disagreements) stored under `message.metadata["multi_model"]` for telemetry/debug.

### Reducers
- `MajorityReducer`: token-level n-gram voting, fallback to highest confidence.
- `WeightedReducer`: weight per variant + self-reported confidence.
- `CriticReducer`: dedicated critic branch reviews other outputs, can trigger retries via `branch.retry()`.
- Reducers can be extended by users (`@multi.reducer` decorator) similar to tools.

### Failure Modes & Recovery
- Branch timeout/exception: mark as `failed`, reducer decides to proceed or trigger fallback variant.
- All fail: escalate to fallback models (existing `fallback_models`) before surfacing error.
- Tool conflicts: orchestrator applies deterministic ordering (planner -> critic -> writer) and logs conflicts in telemetry.

### Testing Strategy
1. Unit tests for `MultiModelStrategy` orchestrator (branch spawning, shared history, tool routing) with fake models.
2. Reducer-specific tests ensuring deterministic merges.
3. Integration test with three mock models verifying final transcript + metadata.
4. Load test covering simultaneous multi-model calls with `max_parallel` throttling.

## 3. Stateful Planning Documents
### Goals
1. Provide a first-class `PlanningDocument` resource combining stateful documents with agent modes/workflows.
2. Enforce entry actions (reading plan, selecting next task), mid-stage task syncing, and exit rituals (marking completion, updating doc).
3. Support multi-phase, multi-session efforts with persisted status and acceptance criteria.

### Data Model
```python
from good_agent.resources import PlanningDocument

plan = PlanningDocument.from_yaml(
    path="plans/feature_x.yaml",
    schema={
        "phases": [
            {
                "name": str,
                "goal": str,
                "acceptance": list[str],
                "steps": [
                    {
                        "id": str,
                        "description": str,
                        "status": Literal["pending", "in_progress", "blocked", "done"],
                        "mandatory": bool,
                    }
                ],
            }
        ],
        "exit_hooks": list[str],
    },
)
```
- Backed by existing stateful resource infra (context-managed tool injection, `context_mode`). Adds semantic helpers: `next_step()`, `mark_step(id, status)`, `phase_completed(phase_id)`.

### Agent Workflow
```python
async with Agent("Implement feature X", modes=["planner"], resources=[plan]) as agent:
    async with plan.enter(agent, phase="phase-1") as session:
        # Entry guard: agent must call plan.summarize_phase() before continuing
        tasks = await session.bootstrap_todos(mode="internal")
        # Agent proceeds with normal work; session ensures periodic sync
        ...
```
1. `plan.enter()` returns a context manager that:
   - Injects planner-specific system prompt additions (phase summary, acceptance criteria, current blockers).
   - Adds temporary tools: `plan.next_task`, `plan.update_step`, `plan.append_notes`.
   - Registers exit hooks (e.g., `session.require_update()` ensures doc is updated before exit completes).
2. Entry validation ensures agent reads doc (auto-call to `plan.render_summary()`), extracts mandatory steps, and seeds agent’s internal TODOs.
3. Exit stage enforces completion criteria + optional scripted actions (e.g., `plan.sync_repo_notes()` or `agent.call("Summarize progress")`).

### Mode Integration
- Provide `agent.modes.add('planning-session')` helper that automatically wraps `plan.enter` and configures work-mode prompts (similar to existing `code-review`).
- Modes can require the plan resource (raise if missing).

### Persistence & Telemetry
- `PlanningDocument` tracks `session_log` entries (phase, steps touched, exit summary) and emits them to telemetry for resuming future sessions.
- Supports `context_mode='delta'` to only emit changed sections back to LLM for long docs.

### Testing Strategy
1. Resource unit tests around parsing, entry/exit requirements, and todo bootstrapping.
2. Mode integration tests ensuring agents can’t exit without updating doc when required.
3. Regression tests for multi-session continuity (simulate two sessions updating same plan file).

## 4. Open Questions / Follow-ups
1. Should branch tool intents be surfaced to users for auditing before execution (e.g., via telemetry flag)?
2. How do we expose branch-level costs to `usage`—aggregate only, or per-variant breakdown?
3. Planning docs: do we constrain schema to YAML/JSON, or allow arbitrary Renderable templates with embedded metadata blocks?
4. Need decision on default reducer (majority vs critic) and whether users can declare reducer per-call vs per-agent config.
5. Determine whether plan exit hooks can trigger external automations (e.g., create ticket) or stay in-process initially.
