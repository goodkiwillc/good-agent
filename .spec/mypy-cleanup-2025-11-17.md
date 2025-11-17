## Overview
Resolve the current `uv run mypy src --check-untyped-defs` failures blocking CI. Focus on aligning subclass signatures, constraining runtime state, and tightening typing for decorators, tool manager wiring, message containers, and spec agent orchestration.

## Requirements
- Fix `MarkdownLinkPattern.handleMatch` so it matches the upstream signature and type contracts.
- Ensure `SyncBridge` never calls `create_task` on a `None` event loop.
- Update event-router decorators to avoid unsafe `__init__` access and enforce awaitable returns.
- Provide precise typing for `MCPClientManager.connect_servers`, `MessageList.append`, and spec agent constructs (`Agent.pipeline`, `.then`, search callable definitions, pattern matches).
- Preserve existing runtime behavior; only adjust control flow if necessary for type safety.

## Implementation Notes
- Inspect `markdown.py` to determine whether the project uses `markdown.inlinepatterns.LinkPattern` or a custom base; mirror its `handleMatch` signature and return types, using overloads if required.
- In `SyncBridge`, guard `loop.create_task` invocations by ensuring `loop` is not `None`; propagate explicit errors when missing.
- For decorators, prefer protocol or callable type hints. Wrap non-awaitable results with `asyncio.ensure_future` or coerce via helper to guarantee an `Awaitable`.
- Introduce lightweight TypedDict / dataclass definitions where `dict[str, Any]` currently masquerades as configs (e.g., MCP server config) to satisfy typing expectations.
- In `message_list.py`, ensure the list generic matches `Message` concrete type or narrow the append input type via `TypeVar` constraints.
- Review `spec.py` pattern matching and helper pipelines; add protocols or generics so `Agent` exposes `.pipeline` / `.then` in typed contexts, or gate those blocks to instances supporting those attrs.

## Todo List
1. Update `src/good_agent/core/markdown.py` to align `handleMatch` signature.
2. Guard `loop.create_task` usage in `src/good_agent/core/event_router/sync_bridge.py`.
3. Refine typing and await handling in `src/good_agent/core/event_router/decorators.py`.
4. Tighten `connect_servers` arguments in `src/good_agent/tools/tools.py`.
5. Fix `MessageList` generics in `src/good_agent/messages/message_list.py`.
6. Resolve `spec.py` typing issues (search callable, pattern matching, agent chaining APIs).
7. Re-run `uv run mypy src --check-untyped-defs` and confirm clean output.

## Testing Strategy
- Primary: `uv run mypy src --check-untyped-defs`.
- If decorator or async behavior changes, run focused unit tests (`pytest tests/core/event_router -k decorator`) to ensure runtime parity.
