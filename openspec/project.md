# Project Context

## Purpose
Good Agent is an async-first Python framework for building composable, stateful AI agents. It focuses on giving developers fine-grained control over an agent's lifecycle, context, tool execution, and orchestration so the same primitives can power CLIs, back-end services, and multi-agent workflows. The project aims to keep the ergonomics "Pythonic" (context managers, decorators, typing) while remaining model/provider agnostic.

## Tech Stack
- Python 3.14+ managed with `uv` (build backend `uv_build`)
- Async IO throughout the core (`async with Agent(...)` usage, `async for agent.execute()` streaming)
- Core dependencies: `good-common`, `pydantic>=2`, `litellm` (provider abstraction), `instructor`, `prompt-toolkit`, `rich`, `jinja2`, `markdown`, `numpy`
- CLI/packaging: `good-agent` console script, `prompt-toolkit` UI, `rich` rendering
- Dev toolchain: `ruff` for linting, `mypy` for type checking, `pytest` + `pytest-asyncio` + `pytest-timeout`, `coverage`, `vcrpy`, `mkdocs` for docs, `watchdog` for live reload
- External integrations: MCP servers, LiteLLM-supported LLM providers, file-type detection via `python-magic`

## Project Conventions

### Code Style
- Target Python 3.14 features (match `tool.ruff.target-version = "py314"`).
- Keep modules fully typed: prefer `typing`/`pydantic` models, annotate async APIs, and use `cast`/`TypeAlias` when inference breaks (documented throughout `src/good_agent`).
- Enforce Ruff with `uv run ruff check src scripts tests`; respect 100-char lines, grouped imports (stdlib/third-party/local), and avoid unnecessary ternaries per Ruff config.
- Async I/O for anything that may block; expose tools/components via decorators with concise docstrings; minimize comments (only when intent is non-obvious).
- Follow "modify existing code" rule: extend current abstractions (`Agent`, `Component`, `tool`) rather than duplicating files or creating `_v2` variants.

### Architecture Patterns
- **Agents as context managers**: `Agent` instances are `async with`-managed, and can fork/branch contexts (`agent.mode("name")`, `agent.branch`, `agent.isolated`).
- **Composable tooling**: Tools are registered via `@tool` (FastDepends-style DI). Components register hooks and expose tools, with dependency resolution handled by `ComponentRegistry`.
- **Mode + event system**: Modes must yield control (generator style) and can be stacked; events emitted through `good_agent.events` let components observe lifecycle.
- **State projection**: Message history is a projection over agent state, supporting snapshots/versioning, branching, and multi-agent piping (`agent_a | agent_b`).
- **CLI-first ergonomics**: `good-agent run` loads saved agents or factory functions with runtime overrides; CLI uses same agent core as library consumers.

### Testing Strategy
- Tests live under `tests/` and run via `uv run pytest -q` (CI default); asyncio tests rely on `pytest-asyncio` with `asyncio_mode = auto`.
- Markers (`unit`, `integration`, `slow`, `llm`, `performance`, `requires_signals`, etc.) gate expensive suites; default PyPI/CI runs exclude `slow` and `llm` unless explicitly requested.
- VCR harness (`vcrpy`, `llm_vcr` fixtures) records LLM interactions; prefer agent-native mocking when practical, but honor existing VCR approach until unified.
- Coverage enforced at ≥65% (`tool.coverage.report.fail_under`); run `uv run coverage run -m pytest` + `coverage report` when adjusting instrumentation-heavy code.
- Static checks: `uv run ruff check ...` for linting and `uv run mypy src tests` for typing before merging; keep doc examples in sync with runnable tests (`docs/`, `examples/`).

### Git Workflow
- Default branch is `main`; feature work happens on short-lived branches named after the OpenSpec `change-id` (verb-led kebab case, e.g., `add-streaming-mode`).
- Specs drive implementation: create/modify `openspec/changes/<change-id>/` (proposal + tasks + deltas) and run `openspec validate <change-id> --strict` before coding/PRs.
- Commits use concise, imperative prefixes (`feat:`, `fix:`, `refactor:`, `docs:` optional) mirroring existing history; avoid stacking unrelated changes.
- Pull requests should reference the relevant change-id and ensure `tasks.md` is fully checked off; archive specs post-deploy via `openspec archive`.

## Domain Context
The framework targets engineers orchestrating multi-step AI workflows (researchers, CLI tooling, multi-agent pipelines). Agents encapsulate prompts, memory, and tools while supporting streaming execution, dependency-injected tools, structured outputs, and MCP/LiteLLM connectivity. Components provide reusable behaviors (memory, telemetry, skill registries), and the CLI exposes these agents interactively for GoodKiwi/Droid operations.

## Important Constraints
- Python 3.14 is the floor; ensure dependencies are compatible (override `grpcio>=1.76.0`).
- Always honor OpenSpec gating: no implementation without an approved proposal except bug fixes/docs.
- Run lint (`uv run ruff check`), type check (`uv run mypy`), and tests (`uv run pytest ...`) before completion; keep logs quiet unless failures occur.
- Avoid logging or committing secrets/API keys; follow security/perf guidance (flag O(n²)+ risks, no destructive external DB writes without explicit approval).
- Documentation/README updates happen only when explicitly requested; focus on modifying existing abstractions rather than duplicating code.

## External Dependencies
- **LiteLLM**: single abstraction over OpenAI/Anthropic/Azure/etc. used by the Agent core; requires appropriate API keys configured via `good-agent config`.
- **Good Common & Instructor**: shared utilities and structured-output helpers leveraged throughout the agent/context pipeline.
- **MCP (Model Context Protocol)** servers: optional tool integrations loaded via configuration.
- **Prompt Toolkit & Rich**: power the interactive CLI (input handling, markdown rendering, panels).
- **Python-magic / lxml / markdown / jinja2**: text+HTML parsing, templating, and file-type inference for tools/components.
