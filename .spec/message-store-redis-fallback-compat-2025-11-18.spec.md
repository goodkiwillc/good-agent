## Overview

Two regressions surfaced in the message subsystem test suite:

1. `tests/unit/messages/test_message_store.py::TestInMemoryMessageStore::test_redis_fallback_on_get` still expects `aget` to raise `MessageNotFoundError` whenever the message is only present in Redis. The production implementation now hydrates the message via `MessageFactory.from_dict`, caches it in memory, and returns it without error. The test must assert the modern contract instead of expecting an exception.
2. `tests/unit/messages/test_messages.py::TestMessageCompatibility::test_message_without_content` simulates a legacy persisted message (no `content_parts`) via `copy_with(content_parts=[])`. Rendering such a message currently yields an empty string because we discard the legacy `content` payload during cloning. The base `Message` type needs a compatibility fallback so `.content`/`.render()` still produce the original text when no parts are available.

## Requirements

1. Update the Redis fallback test to verify that `aget` deserializes, returns, and caches the Redis payload instead of raising `MessageNotFoundError`.
2. Add a legacy-content fallback path to `good_agent.messages.base.Message` so that:
   - When a message is constructed (or cloned) without `content_parts` but with historical `content` data, that text is preserved.
   - `.render()`/`.content` return the preserved text whenever no content parts exist.
   - `Message.copy_with` propagates the original textual content when content parts are stripped to mimic legacy data.
3. Avoid introducing new dependencies or altering the public API beyond the backwards-compatibility fix.

## Implementation Notes

- Extend `Message` with a private `_legacy_content_fallback` attribute. Capture any supplied `legacy_content` kwarg and/or the string derived from the original `content` argument so we always have a textual backup.
- After initialization, if `content_parts` is empty but we have captured fallback text, store it in `_legacy_content_fallback`. In `render`, when no parts exist, return this fallback (or `_raw_content`) instead of an empty string.
- Update `copy_with` to forward the current rendered content via a `legacy_content` kwarg whenever we rebuild the message (especially when custom `content_parts` are provided). This ensures clones created solely to zero out parts retain their textual representation.
- Revise `test_redis_fallback_on_get` to assert the positive path: the mock Redis payload should deserialize into a `UserMessage`, land in the in-memory cache, and be retrievable without raising. Validate that the Redis client was called with the expected key and that a subsequent `store.exists` succeeds.

## Todo List

1. [ ] Add `_legacy_content_fallback` handling and fallback rendering logic to `good_agent/messages/base.py`.
2. [ ] Ensure `Message.copy_with` passes the fallback content when cloning (especially when overriding `content_parts`).
3. [ ] Update `tests/unit/messages/test_message_store.py::test_redis_fallback_on_get` to assert successful Redis hydration.
4. [ ] Re-run the affected pytest modules plus repo linters/type-checkers.

## Testing Strategy

- `uv run pytest tests/unit/messages/test_message_store.py::TestInMemoryMessageStore::test_redis_fallback_on_get -vv`
- `uv run pytest tests/unit/messages/test_messages.py::TestMessageCompatibility::test_message_without_content -vv`
- Full suite for safety: `uv run pytest tests/unit/messages -vv`
- Static analysis: `uv run ruff check` and `uv run mypy`
