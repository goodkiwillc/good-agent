# Change: Agent Hooks Accessor

## Why

The current `agent.on()` method requires developers to know exact event names and manually look up TypedDict types. The existing `TypedEventHandlersMixin` is defined but not integrated into Agent. A dedicated `agent.hooks` accessor would provide type-safe, discoverable event handler registration with clear documentation of event semantics.

## What Changes

- Create `HooksAccessor` class with typed methods for all events
- Add `agent.hooks` property to Agent class
- Each method documents whether the event is interceptable
- Each method has proper type hints for `EventContext[ParamsType, ReturnType]`
- Deprecate `TypedEventHandlersMixin` in favor of `agent.hooks`

## Impact

- Affected specs: events
- Affected code:
  - `src/good_agent/agent/hooks.py` (new file)
  - `src/good_agent/agent/core.py` - add hooks property
  - `src/good_agent/agent/__init__.py` - export HooksAccessor
  - `src/good_agent/events/decorators.py` - deprecate TypedEventHandlersMixin
- Breaking: None (additive, deprecation only)
- Dependencies: Requires Phase 1, 2, and 3
