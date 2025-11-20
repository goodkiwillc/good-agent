# Documentation Hallucinations / Discrepancies

The following features are documented in `docs/` or `AGENTS.md` but are not present in the design specification `.spec/v1/DESIGN.md`.

## 1. Todo List Management
**Source:** `docs/features/tasks.md`
**Details:** Describes a `TaskManager` extension (`good_agent.extensions.TaskManager`) and `ToDoItem` for managing todo lists. This component and functionality are not in the design spec.

## 2. Advanced Human-in-the-Loop Features
**Source:** `docs/features/human-in-the-loop.md`
**Details:**
- `@agent.route` decorator for defining interaction flows.
- `ctx.ask_user()` and `ctx.show_and_ask()` methods on the context.
- `ctx.llm_call()` within routes.
- `WebUI` and `SlackBot` integrations.
**Note:** The design spec only mentions `agent.user_input`.

## 3. Agent Facades
**Source:** `docs/api-reference.md`, `docs/features/tasks.md`
**Details:** The documentation describes several "facades" that are not in the design spec:
- `agent.tasks` (e.g., `agent.tasks.create` vs `agent.create_task` in spec).
- `agent.events` (e.g., `agent.events.apply` vs `agent.do` in spec).
- `agent.tool_calls` (not in spec).
- `agent.context_manager` (not in spec).
- `agent.versioning` (Spec mentions `agent.version_id` and `revert_to_version`, but `api-reference.md` calls it a facade `AgentVersioningManager`).

## 4. Agent Configuration Manager
**Source:** `docs/api-reference.md`
**Details:** `agent.config` attribute returning an `AgentConfigManager`. Not in design spec.

## 5. Interactive Execution Details
**Source:** `docs/features/interactive-execution.md`
**Details:** While `agent.execute` is in the spec, the doc describes specific properties like `message.iteration_index` and `message.tool_response` which are not explicitly detailed in the spec (though arguably implementation details).
