## Feature Spec Reference

### Purpose
- Provide a quick refresher on the current Good Agent architecture before planning a new feature.
- Capture the conventions that keep API designs async-first and Python-native (context managers, decorators, typed resources).
- Offer a repeatable outline for drafting `.spec/v1/features/**/*.md` documents.

### Architectural Touchpoints (See `.spec/v1/DESIGN.md` for detail)
- **Agent lifecycle**: `async with Agent(...)` is the canonical entry point; specs should assume context-managed resources and explicit startup/shutdown semantics.
- **Message model**: History slices (`agent[-1]`, `agent.user`, `agent.assistant`) and structured messages (`AssistantMessage`, `ToolMessage`) enable deterministic flows; specs must preserve typed message access.
- **Tooling system**: Tools can be async callables, `@tool`-decorated methods on `AgentComponent`s, or MCP-backed registries; favor declarative registration and dependency injection via FastDepends.
- **Routing & modes**: Modes (`@agent.mode`), context pipelines, transitions, and command exposure provide reusable behaviors. New specs should design around these primitives rather than bespoke orchestration.
- **Stateful resources**: `EditableYAML`, planning documents, and similar context managers swap in scoped toolsets. Reference this pattern when a feature requires multi-step state mutation.
- **Transcripts & testing**: Transcript recorder/replayer and pytest fixtures mock only the LLM layer. New features should specify how they integrate with transcripts and testing tiers.
- **Multi-agent patterns**: Pipe operator (`agent_a | agent_b`), remote agent transports, and sub-agent modes allow composition—describe how a feature behaves within these graphs.

### API & Interface Principles
- **Async-first**: All new public APIs should be `async`, integrate with event loops cleanly, and avoid hidden synchronous I/O.
- **Context managers**: Prefer `async with` wrappers for resources, modes, and temporary configuration.
- **Python-native ergonomics**: Use decorators (`@agent.route`, `@agent.modes.add`, `@tool`, `@command`) and descriptors over string-based registration when possible.
- **Typed contracts**: Leverage Pydantic models, `Renderable` templates, and structured tool responses to communicate schemas explicitly.
- **Composable context**: Design functions so they can operate with existing context pipeline hooks and dependency injection (FastDepends, `Context(...)`).
- **Orchestration compatibility**: Ensure features respect router decisions, agent history transformations, and telemetry hooks; avoid hard-coding control flow.

### Suggested Spec Outline
1. **Overview** – Succinct goal and the architectural areas impacted.
2. **Requirements & Constraints** – Explicit async, Pythonic, and testing expectations.
3. **Current Architecture Hooks** – Which components from DESIGN.md the feature extends (e.g., routing, resources, transcripts).
4. **API Sketches** – Python-first examples (context managers, decorators, async methods) demonstrating usage.
5. **Lifecycle & State** – How the feature behaves across `async with` scopes, message history, and tool execution.
6. **Testing Strategy** – Transcript integration, pytest fixture usage, telemetry validation.
7. **Open Questions / TODOs** – Items to resolve before implementation.

### Pre-Spec Checklist
- [ ] Re-read relevant sections of `.spec/v1/DESIGN.md` to confirm compatibility.
- [ ] Identify overlapping feature specs in `.spec/v1/features/` and note shared abstractions.
- [ ] Validate that proposed APIs can run under mocked LLMs and transcript replay.
- [ ] Plan for dependency injection (components, tools, transports) rather than direct instantiation.
- [ ] Confirm telemetry, configuration, and error-handling surfaces align with existing patterns.

### When in Doubt
- Prefer extending routers, context pipelines, or components over creating parallel systems.
- Reach for typed resources (`Renderable`, `AgentComponent`, stateful resources) before ad hoc dicts.
- Document how humans or orchestrators interact with the feature (commands, interactions, blocking policies).
- Keep the spec iterative—capture MVP plus phased enhancements aligned with architecture.
