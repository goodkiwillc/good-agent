# Tasks: Event Classification and Registry

## 1. Create Event Semantics Classification
- [ ] 1.1 Create `events/classification.py`
- [ ] 1.2 Define `EventSemantics` Flag enum (INTERCEPTABLE, SIGNAL)
- [ ] 1.3 Create `EVENT_SEMANTICS` dict mapping all events
- [ ] 1.4 Classify all `:before` events as INTERCEPTABLE
- [ ] 1.5 Classify all `:after` events as SIGNAL
- [ ] 1.6 Classify error events appropriately (some interceptable)

## 2. Create Event Registry
- [ ] 2.1 Create `events/registry.py`
- [ ] 2.2 Create `EVENT_PARAMS` dict mapping events to TypedDicts
- [ ] 2.3 Add `get_params_type()` helper function
- [ ] 2.4 Add `get_event_semantics()` helper function
- [ ] 2.5 Export from `events/__init__.py`

## 3. Clean Up Deprecated Events
- [ ] 3.1 Remove `TOOL_RESPONSE` (use `TOOL_CALL_AFTER`)
- [ ] 3.2 Remove `TOOL_ERROR` (use `TOOL_CALL_ERROR`)
- [ ] 3.3 Remove `EXECUTE_START` (use `EXECUTE_BEFORE`)
- [ ] 3.4 Remove `EXECUTE_COMPLETE` (use `EXECUTE_AFTER`)
- [ ] 3.5 Remove `EXECUTE_ITERATION` (use specific phase events)
- [ ] 3.6 Remove `EXECUTE_ITERATION_START` (use `EXECUTE_ITERATION_BEFORE`)
- [ ] 3.7 Remove `EXECUTE_ITERATION_COMPLETE` (use `EXECUTE_ITERATION_AFTER`)
- [ ] 3.8 Remove `CONTEXT_PROVIDER_CALL` (use `CONTEXT_PROVIDER_BEFORE`)
- [ ] 3.9 Remove `CONTEXT_PROVIDER_RESPONSE` (use `CONTEXT_PROVIDER_AFTER`)
- [ ] 3.10 Remove `TEMPLATE_COMPILE` (use specific phase events)

## 4. Document Extension Point Events
- [ ] 4.1 Add docstrings to Storage events noting they are extension points
- [ ] 4.2 Add docstrings to Cache events noting they are extension points
- [ ] 4.3 Add docstrings to Validation events noting they are extension points
- [ ] 4.4 Add docstrings to Summary events noting they are extension points

## 5. Testing
- [ ] 5.1 Test `get_params_type()` returns correct types
- [ ] 5.2 Test `get_event_semantics()` returns correct classification
- [ ] 5.3 Verify all events are in registry
- [ ] 5.4 Run existing tests to catch any deprecated event usage

## 6. Migration
- [ ] 6.1 Search codebase for deprecated event usage
- [ ] 6.2 Update any internal usage to new names
- [ ] 6.3 Add deprecation warnings if keeping aliases temporarily
