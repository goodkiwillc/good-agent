## Overview
- Diagnose why `uv run pytest tests/unit/core/test_markdown_extensions.py` hangs instead of completing.
- Focus on the citation preprocessor/manager pipeline since the tests exercise those components directly.

## Requirements
1. Determine the exact code path causing the hang without relying solely on blind pytest execution.
2. Instrument or isolate the suspect components to reproduce the blocking behavior deterministically.
3. Implement a fix that ensures the markdown extension tests run to completion.
4. Keep changes minimal and aligned with existing coding patterns.

## Implementation Notes
- Prioritize static analysis of `tests/unit/core/test_markdown_extensions.py` and `src/good_agent/core/markdown.py` before running tests.
- Check for infinite loops, blocking I/O, or recursive markdown processing triggered by `CitationManager` registration.
- Consider running pytest with focused options (e.g., `-k citation -vv --maxfail=1`) once instrumentation/logging is ready to capture the hang point.
- Verify whether any global markdown extension state leaks between tests, leading to re-entrancy or deadlocks.

## Todo List
 - [ ] Inspect markdown citation extension implementations for blocking constructs or shared state.
 - [ ] Trace pytest fixtures and setup used by the markdown tests to spot potential waits.
 - [ ] Instrument or narrow-run pytest to capture where execution halts.
 - [ ] Apply fix ensuring citation processing terminates cleanly.
 - [ ] Extend/adjust tests to cover the fixed scenario.
 - [ ] Run validators (ruff, type checks, targeted pytest) and ensure passing results.

## Testing Strategy
- After fixing, execute `uv run ruff check` and any relevant type checks (e.g., `uv run ruff check --select=I` if imports affected).
- Run the targeted pytest module: `uv run pytest tests/unit/core/test_markdown_extensions.py -vv`.
- If changes impact broader markdown functionality, run nearby suites (`tests/unit/core/test_markdown*.py`).
