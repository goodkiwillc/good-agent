# Tasks: Event Classification and Registry

## 1. Create Event Semantics Classification
- [x] 1.1 Create `events/classification.py`
- [x] 1.2 Define `EventSemantics` Flag enum (INTERCEPTABLE, SIGNAL)
- [x] 1.3 Create `EVENT_SEMANTICS` dict mapping all events
- [x] 1.4 Classify all `:before` events as INTERCEPTABLE
- [x] 1.5 Classify all `:after` events as SIGNAL
- [x] 1.6 Classify error events appropriately (some interceptable)

## 2. Create Event Registry
- [x] 2.1 Create `events/registry.py`
- [x] 2.2 Create `EVENT_PARAMS` dict mapping events to TypedDicts
- [x] 2.3 Add `get_params_type()` helper function
- [x] 2.4 Add `get_event_semantics()` helper function
- [x] 2.5 Export from `events/__init__.py`

## 3. Clean Up Deprecated Events
- [x] 3.1 Remove `TOOL_RESPONSE` (use `TOOL_CALL_AFTER`)
- [x] 3.2 Remove `TOOL_ERROR` (use `TOOL_CALL_ERROR`)
- [x] 3.3 Remove `EXECUTE_START` (use `EXECUTE_BEFORE`)
- [x] 3.4 Remove `EXECUTE_COMPLETE` (use `EXECUTE_AFTER`)
- [x] 3.5 Remove `EXECUTE_ITERATION` (use specific phase events)
- [x] 3.6 Remove `EXECUTE_ITERATION_START` (use `EXECUTE_ITERATION_BEFORE`)
- [x] 3.7 Remove `EXECUTE_ITERATION_COMPLETE` (use `EXECUTE_ITERATION_AFTER`)
- [x] 3.8 Remove `CONTEXT_PROVIDER_CALL` (use `CONTEXT_PROVIDER_BEFORE`)
- [x] 3.9 Remove `CONTEXT_PROVIDER_RESPONSE` (use `CONTEXT_PROVIDER_AFTER`)
- [x] 3.10 Remove `TEMPLATE_COMPILE` (use specific phase events)

## 4. Document Extension Point Events
- [x] 4.1 Add docstrings to Storage events noting they are extension points
- [x] 4.2 Add docstrings to Cache events noting they are extension points
- [x] 4.3 Add docstrings to Validation events noting they are extension points
- [x] 4.4 Add docstrings to Summary events noting they are extension points

## 5. Testing
- [x] 5.1 Test `get_params_type()` returns correct types
- [x] 5.2 Test `get_event_semantics()` returns correct classification
- [x] 5.3 Verify all events are in registry
- [x] 5.4 Run existing tests to catch any deprecated event usage

## 6. Migration
- [x] 6.1 Search codebase for deprecated event usage
- [x] 6.2 Update any internal usage to new names
- [x] 6.3 Add deprecation warnings if keeping aliases temporarily
