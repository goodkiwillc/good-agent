# Change: Complete Event Coverage

## Why

Several events are defined in `AgentEvents` but never dispatched, and some important lifecycle events are missing entirely. This creates gaps in the event system that prevent components from hooking into key moments in the agent lifecycle.

## What Changes

- Add `EXECUTE_ITERATION_AFTER` dispatch after each iteration completes
- Add `EXECUTE_ERROR` dispatch and event for execute() exceptions
- Add `CONTEXT_PROVIDER_AFTER` dispatch after provider returns
- Add `LLM_COMPLETE_ERROR` dispatch (distinct from general `LLM_ERROR`)
- Add `AGENT_CLOSE_BEFORE` and `AGENT_CLOSE_AFTER` events for cleanup hooks
- Make `TOOL_CALL_ERROR` interceptable (allow fallback response)
- Make `EXECUTE_ERROR` interceptable (allow retry/abort)
- Add corresponding TypedDicts for new events

## Impact

- Affected specs: events
- Affected code:
  - `src/good_agent/agent/core.py` - execute loop, close method
  - `src/good_agent/agent/tools.py` - tool error handling
  - `src/good_agent/model/llm.py` - LLM error handling
  - `src/good_agent/extensions/template_manager/core.py` - context provider
  - `src/good_agent/events/agent.py` - new event definitions
  - `src/good_agent/events/types.py` - new TypedDicts
- Breaking: None (additive changes)
- Dependencies: Requires Phase 1 (refactor-event-foundation)
