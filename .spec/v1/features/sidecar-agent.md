# Sidecar Agent Orchestration Feature Spec

## Overview
- Introduce a companion "sidecar" agent that co-runs with a primary `Agent` to enforce workflow discipline, surface relevant tooling, and capture reusable execution patterns.
- Scope covers declarative attachment of a sidecar, bidirectional messaging primitives between the primary agent and sidecar, and shared state facilities for checklists, specs, and telemetry.
- Target outcomes: reduce cognitive load for the primary agent, improve adherence to local instructions, and seed a knowledge base of successful prompt/tool combinations.

## Requirements & Constraints
- Must operate fully async and integrate with `async with Agent(...)` lifecycle without blocking message execution.
- Sidecar responsibilities:
  - Tool selection assistance via MCP-aware filtering/annotation before each `agent.call()` or `agent.execute()` step.
  - Compliance guardrails that can veto/flag deviations from route/mode constraints and enforce TODO/spec updates.
  - Persistent working-doc updates (e.g., `.spec`, todo lists) mediated through existing editable resources (`EditableYAML`, planning docs) rather than bespoke file I/O.
  - Pattern capture that records successful prompts/tool chains into a structured store (Renderable transcript section or dedicated resource).
- Respect existing router, transcript, and telemetry hooks; no direct global state.
- Configuration must allow opting into lighter-weight models or local heuristics for the sidecar without exposing API keys.
- Fail-safe design: if the sidecar errors, the primary agent must continue with logged warnings.

## Current Architecture Hooks
- **Agent lifecycle**: attach sidecar via `async with Agent(..., sidecar=SidecarConfig(...))` ensuring shared context managers initialize/teardown together.
- **Tooling system**: sidecar extends `ToolManager` or provides a filtered view (e.g., `agent.tools.with_filters(...)`) before dispatch; leverages FastDepends for dependency injection.
- **Routing & modes**: implement as an `AgentComponent` that subscribes to route transitions, allowing enforcement of mode-specific policies.
- **Stateful resources**: reuse `EditableYAML`, planning document contexts, and transcript recorder for sidecar-authored artifacts.
- **Telemetry**: hook into telemetry events to log sidecar interventions, tool recommendations, and compliance violations.

## API Sketches
```python
from good_agent import Agent, SidecarConfig
from good_agent.sidecars import ComplianceSidecar

sidecar = SidecarConfig(
    factory=ComplianceSidecar,
    model="gpt-4o-mini",
    objectives=["tool_selection", "todo_enforcement", "pattern_capture"],
)

async with Agent(
    "You are the primary execution agent.",
    tools=[...],
    sidecar=sidecar,
) as agent:
    agent.append("Plan and execute the task list in TODO.md")
    response = await agent.call()

    await agent.sidecar.record_pattern(
        task="lint+test",
        prompt=agent[-1].content,
        tools=agent.tools.last_used(),
    )

```

```python
@agent.route("/research")
async def research_mode(agent: Agent):
    async with agent.sidecar.guardrails(mode="research"):
        async for message in agent.execute():
            if message.role == "assistant":
                await agent.sidecar.ensure_spec_updated(section="Findings")
```

## Lifecycle & State
- Initialization: sidecar instantiated during `Agent.__aenter__`, receives references to Agent context, tool registry, telemetry publisher, and planning docs.
- Per-turn flow:
  1. Primary agent emits intent (route + planned action).
  2. Sidecar evaluates tool filters and surfaces ranked tool list via structured metadata.
  3. Sidecar updates checklist/spec state prior to invoking the LLM, optionally appending assistant directives.
  4. After each message/tool call, sidecar validates adherence rules and records patterns.
- Shutdown: sidecar flushes buffered pattern captures to durable resources, finalizes todo/spec status, and detaches gracefully.
- Error handling: exceptions inside sidecar transitions translate into telemetry warnings and optional fallback to passive mode.

## Testing Strategy
- Extend transcript-based tests to include sidecar intervention records, ensuring deterministic replays with mocked sidecar responses.
- Pytest fixtures provide `FakeSidecar` implementations to assert enforcement logic (e.g., blocked tool usage when outside whitelist).
- Add integration tests covering `agent.execute()` loops with sidecar guardrails, verifying TODO/spec updates via temporary files.
- Include property-based tests for tool filtering and pattern-capture schema validation.

## Open Questions / TODOs
- [ ] Determine storage format/location for pattern captures (telemetry stream vs. dedicated resource file).
- [ ] Define minimal sidecar interface: message hooks, tool filtering API, and spec/todo update protocols.
- [ ] Decide whether sidecar runs via lightweight LLM calls, deterministic heuristics, or hybrid approach.
- [ ] Establish rate limits and concurrency behavior when multiple sidecars are attached in inter-agent pipelines.
- [ ] Clarify security boundaries for MCP tool metadata shared with the sidecar.


----

API Ideation:

```python


class GuardRailDecision(BaseModel):
    decision: Literal["allow", "warn", "block"]
    reason: str

class SidecarAgent(Agent):

    @on(AgentEvents.MESSAGE_APPEND_BEFORE)
    async def on_assistant_message(
        self,
        message: AssistantMessage,
        agent: Agent,
    ):

        response = await self.call(
            'Evaluate the following assistant message for compliance with the relevant policies: ',
            '{{policies}}',
            '{{message}}',
            policies=agent.sidecar.get_active_policies(),
            message=message.content,
            response_model=GuardRailDecision,
        )

        match response.output.decision
            case 'allow':
                pass  # proceed as normal
            case 'warn':
                agent.append(
                    "<system>Warning: The previous assistant message may violate compliance policies.</system>",
                    role="system"
                )
            case 'block':
                self.block(
                    'Assistant message blocked by sidecar compliance check: {{reason}}',
                    reason=response.reason
                )
                # raise SidecarComplianceError("Assistant message blocked by sidecar compliance check."




guardrails_sidecar = Agent(
    model='gpt-4o-mini',
)

# limits to just a single sidecar

agent = Agent(
    'system prompt',
    model='gpt-4',
    tools=[...],
    sidecar=guardrails_sidecar,
)


```
