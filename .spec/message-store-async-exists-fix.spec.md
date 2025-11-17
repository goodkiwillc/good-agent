## Overview

`tests/unit/messages/test_message_store.py::TestInMemoryMessageStore::test_async_operations_memory_only` occasionally fails at `assert not await store.aexists(ULID())`. The test assumes a newly generated `ULID()` cannot collide with the ID of the message previously stored in the same test, but in practice we sometimes run suites where `ULID()` is deterministically stubbed (or replays a recorded stream), so the randomly generated value can match the stored message ID. When that happens, `aexists` correctly returns `True`, yet the assertion expects `False`, producing the observed `assert not True` failure.

## Requirements

1. Make the test deterministically select a ULID value that is guaranteed to differ from the stored message ID, even when ULID generation is patched or deterministic.
2. Keep the intent of the test intact: verifying that `aexists` returns `False` for IDs not present in the in-memory cache when no redis backend is configured.
3. Avoid introducing new helpers in production code; keep the change scoped to the test suite.

## Implementation Notes

- After storing the message in the async test, derive a "missing" ULID by flipping the lowest bit of the existing `message.id.bytes` (e.g., via `bytearray` copy) so we know it cannot match anything already persisted.
- Use that deterministic `missing_id` for the negative `aexists` assertion instead of a fresh `ULID()`.
- Keep the rest of the test untouched to ensure previous coverage still holds.

## Todo List

1. [ ] Update `test_async_operations_memory_only` to compute a guaranteed-missing ULID derived from `message.id`.
2. [ ] Re-run the message store unit tests to confirm the flake is resolved.

## Testing Strategy

- `uv run pytest tests/unit/messages/test_message_store.py::TestInMemoryMessageStore::test_async_operations_memory_only -vv`
- Full file run: `uv run pytest tests/unit/messages/test_message_store.py -vv` after edits to ensure no regressions.
