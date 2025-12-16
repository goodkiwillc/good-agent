# Tasks: Agent locking for thread safety

- [ ] Audit current Agent concurrency hotspots (message manager, execute loop, ToolExecutor emissions, mode transitions) to confirm lock insertion points.
- [ ] Introduce an Agent-level async lock (and optional thread-safe proxy) and serialize mutating entrypoints (call/execute/append/replace/mode transitions, tool message emission) while keeping tool execution parallel.
- [ ] Ensure event handlers that mutate Agent state have a way to execute under the guard or are documented as unsafe; align `do`/`apply` usage accordingly.
- [ ] Add tests covering overlapping `execute`/`call`, parallel tool execution with ordered emissions, and cross-thread submissions using the proxy.
- [ ] Run validators: `uv run ruff check`, `uv run mypy src tests`, `uv run pytest` (appropriate markers) and fix any failures.
