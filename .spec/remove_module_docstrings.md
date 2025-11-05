## Overview
Remove module-level triple-quoted docstrings that precede the first import across all Python modules in the repository per user request.

## Requirements
- Delete only triple-quoted module docstrings appearing before the first import statement.
- Preserve shebangs, encoding declarations, and comment lines.
- Avoid altering inline or function/class docstrings.
- Maintain existing imports, exports, and runtime behavior.

## Implementation Notes
- Identify affected files via multiline ripgrep search anchored at file start.
- Confirm each removal keeps surrounding blank lines sensible (no leading double blanks before imports).
- Skip files where the leading string is intentionally used (e.g., `__all__` assignments or metadata) unless it is a pure docstring.

## Todo List
- [ ] Enumerate affected Python files containing leading module docstrings.
- [ ] Remove the leading docstring from each identified file.
- [ ] Ensure formatting remains consistent (single blank line before imports as needed).
- [ ] Run `uv run ruff check` to verify linting passes.
- [ ] Run `uv run pytest` to confirm tests still pass.

## Testing Strategy
- Execute `uv run ruff check` to catch formatting or syntax regressions.
- Execute `uv run pytest` to ensure the test suite remains green after docstring removals.
