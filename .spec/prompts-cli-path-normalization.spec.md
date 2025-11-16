## Overview

Cross-platform users reported failures in the prompts CLI tests where template
names were rendered with platform-specific path separators. The current
implementation relies on `Path.__str__` which introduces `"\\"` on Windows. The
unit suite expects POSIX-style names (e.g., `system/test`), so runs on Windows or
mixed environments break across multiple commands (`list`, `scan`, `history`,
`restore`, `tree`, `snapshot`, and auto-version flows).

## Requirements

- Normalize template identifiers in the index layer to use forward slashes.
- Preserve compatibility with existing `index.yaml` files that may already
  contain backslash-separated paths.
- Ensure metadata reload does not crash when historic timestamps are persisted
  as ISO strings.
- Avoid regressing existing functionality on POSIX platforms.

## Implementation Notes

- Introduce a `_normalize_name()` helper inside `TemplateIndex` to coerce all
  template identifiers to POSIX format.
- Use `Path.with_suffix("")` and `Path.as_posix()` when deriving metadata during
  scans to remove the file extension while standardizing separators.
- Normalize `name` and `path` fields when reading from disk; convert historic
  timestamps back to `datetime` objects so the serializer can safely call
  `.isoformat()`.
- Update existing metadata instances when rescanning to keep `name` and `path`
  in sync with normalized values.

## Todo List

- [ ] Normalize template names and paths during index load.
- [ ] Normalize names during scan for new or modified templates.
- [ ] Ensure historical timestamps load as datetimes for safe re-serialization.
- [ ] Backfill targeted tests to verify CLI behaviour (leveraging existing test
      suite).

## Testing Strategy

- Execute `uv run pytest tests/unit/test_prompts_cli.py::TestPromptsCLI -xvs` to
  confirm all CLI behaviours pass with normalized paths.
- Run the full unit suite if time permits to ensure no regressions in template
  management modules that depend on the index layer.
