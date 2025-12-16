# Change: Event Classification and Registry

## Why

The event system lacks formal classification of event semantics (interceptable vs observational) and there's no programmatic way to discover which TypedDict corresponds to which event. This makes it harder for developers to understand event behavior and write type-safe handlers.

## What Changes

- Add `EventSemantics` Flag enum for classifying events
- Create `EVENT_SEMANTICS` mapping for all events
- Create `EVENT_PARAMS` registry mapping events to TypedDicts
- Add `get_params_type()` helper function
- Clean up deprecated event aliases from `AgentEvents`
- Document extension point events (Storage, Cache, Validation)

## Impact

- Affected specs: events
- Affected code:
  - `src/good_agent/events/classification.py` (new file)
  - `src/good_agent/events/registry.py` (new file)
  - `src/good_agent/events/agent.py` - remove deprecated aliases
  - `src/good_agent/events/__init__.py` - exports
- Breaking: Deprecated event aliases removed (TOOL_RESPONSE, TOOL_ERROR, EXECUTE_START, etc.)
- Dependencies: Requires Phase 1 and Phase 2
