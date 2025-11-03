# Citation Manager Test Plan

## Overview
Comprehensive test suite for CitationManager focusing on **behavioral patterns** rather than internal implementation details.

## Test Files Structure

### 1. `test_citation_manager.py` ✅ PASSING (11/11)
**Core Manager Behavior**
- Manager initialization (default, with shared index)
- Installation on agent
- Public API methods (parse, export, summaries)
- Shared index behavior across managers

**Status**: All tests passing

### 2. `test_citation_parsing.py` ✅ EXISTING
**Content Citation Parsing**
- Markdown format parsing
- LLM format transformation
- XML/href attribute handling
- Malformed citations
- Edge cases (empty content, sparse indices, etc.)

**Status**: Tests already exist and likely passing

### 3. `test_citation_index.py` ✅ EXISTING
**Citation Index Basics**
- Index initialization
- Add/retrieve operations
- Duplicate handling
- Lookup operations

**Status**: Tests already exist and likely passing

### 4. `test_citation_message_lifecycle.py` ⚠️  FAILING (0/12)
**Message Citation Lifecycle**
- Message creation with citations
- Local citation storage (sequential indices)
- Message rendering for DISPLAY mode
- Message rendering for LLM mode (global indices)
- Mixed format handling

**Status**: RED PHASE - All tests failing as expected (event handlers commented out)

**Expected failures:**
- Citations not extracted during message creation
- No transformation during rendering
- Event handlers not firing

### 5. `test_citation_global_index.py` ⚠️ NOT YET RUN
**Global Index Coordination**
- Same URL always gets same global index
- Local-to-global mapping
- Citation lookup from global index
- Sparse index handling
- Index merging

**Status**: Tests written, not yet run

### 6. `test_citation_tool_adapter.py` ⚠️ NOT YET RUN
**Tool Adapter Integration**
- Tool identification (url/urls parameters)
- Signature transformation (url → citation_idx)
- Parameter translation at runtime
- Multiple URLs support
- Adapter enable/disable

**Status**: Tests written, not yet run

### 7. `test_citation_events.py` ⚠️ NOT YET RUN
**EventRouter Integration**
- MESSAGE_CREATE_BEFORE event handling
- MESSAGE_RENDER_BEFORE event handling
- MESSAGE_APPEND_AFTER event handling
- Event ordering and priorities
- Error handling
- Multi-message scenarios

**Status**: Tests written, not yet run

## Key Behavioral Patterns Tested

### 1. Citation Extraction
Messages should automatically extract citations from:
- Markdown reference blocks `[1]: URL`
- Inline URLs `https://...`
- XML url/href attributes `url="..."`
- Mixed formats

### 2. Local Storage
- Messages store LOCAL citation lists (sequential: [0], [1], [2])
- Sparse indices are compacted
- Duplicates within a message are deduplicated

### 3. Global Index
- CitationIndex maintains GLOBAL indices across all messages
- Same URL always gets same global index
- Different URLs get different indices
- Index is sequential starting at 1

### 4. Rendering Transformation
**DISPLAY Mode (for users):**
- `[!CITE_X!]` → `[domain](url)` markdown links
- `idx="X"` → `url="..."` for XML
- Reference blocks removed

**LLM Mode (for models):**
- Local indices → GLOBAL indices
- Format: `[!CITE_X!]` or `idx="X"`
- Consistent indices across conversation

### 5. Tool Integration
- Tools with `url` or `urls` parameters are adapted
- LLM sees `citation_idx`/`citation_idxs` instead
- Adapter translates indices back to URLs at runtime

## Implementation Status

### ✅ Working
- CitationManager initialization
- Parse method (standalone usage)
- Public API methods
- CitationIndex operations
- CitationAdapter code exists

### ⚠️ Not Working (Event Handlers Commented Out)
Lines 122-144 in `manager.py` are commented out:
- `_on_message_create_before` - not registered
- `_on_message_render_before` - not registered
- `_on_message_append_after` - not registered

### 🎯 Next Steps (GREEN PHASE)

1. **Uncomment event handlers** in `manager.py` (lines 122-131)
2. **Run lifecycle tests** - expect some to pass immediately
3. **Fix failing tests** one by one:
   - Debug event handler logic
   - Fix any transformation issues
   - Ensure global index coordination works
4. **Run remaining test suites**
5. **Refactor** as needed

## TDD Cycle

We're currently in **RED PHASE**:
- ✅ Tests written defining expected behavior
- ✅ Tests fail as expected (handlers disabled)
- ⏳ Ready to move to GREEN PHASE (enable handlers, make tests pass)

## Notes

- Agent construction issue: Cannot pass system message during `__init__` - causes assertion error about `_agent` not being set
  - **Workaround**: Use `Agent(extensions=[...])` without system message parameter
  - All tests updated to use this pattern

- Event handler priorities: CitationManager uses priority 150
  - Runs between high-priority (200+) and low-priority (<100) handlers

- The `@on` decorator is used instead of `agent.on()` calls for cleaner code