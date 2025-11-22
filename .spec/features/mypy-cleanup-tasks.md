## Overview
Resolve current mypy failures by aligning TYPE_CHECKING imports with real modules, ensuring helper functions return the declared types, and temporarily disabling third-party integrations that lack type stubs.

## Requirements
- Update `src/good_agent/agent/tasks.py` so type checking uses an existing module path.
- Make `_augment_tool_message_for_context` in `src/good_agent/mock.py` return an actual `ToolMessage` instance while preserving augmented content behavior.
- Comment out the `duckduckgo_search` dependency in `src/good_agent/agents/research.py` per request so mypy stops importing it.
- Keep runtime behavior consistent (context augmentation still works, search_web now clearly reports being disabled).
- Validate with `uv run ruff check .`, `uv run mypy src`, and `uv run pytest -q`.

## Implementation Notes
- Switch the guarded import in `agent/tasks.py` to `good_agent.core.components.AgentComponent`, matching the concrete location already used elsewhere.
- Use `message.copy_with(content=augmented_content)` in `_augment_tool_message_for_context` so the return type remains `ToolMessage` while keeping the immutable pattern.
- Replace the DuckDuckGo block with a short explanatory return message and comment out the old code for easy restoration later.

## Todo List
1. Fix TYPE_CHECKING import path in `agent/tasks.py`.
2. Update `_augment_tool_message_for_context` to return `ToolMessage` copies.
3. Comment out `duckduckgo_search` usage in `agents/research.py` and provide temporary stub behavior.
4. Run `uv run ruff check .`.
5. Run `uv run mypy src`.
6. Run `uv run pytest -q`.

## Testing Strategy
- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest -q`
