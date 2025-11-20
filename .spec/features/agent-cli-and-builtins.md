# Feature Spec: Document CLI & Built-In Agents

**Status**: 📝 Draft  
**Created**: 2025-11-20  
**Author**: Droid  
**Related**: `docs/getting-started/quickstart.md`, `src/good_agent/cli/run.py`, `src/good_agent/agents/`

## Overview

Expand the public documentation to cover the `good-agent run` CLI workflow and the bundled reference agents so that new users can quickly experiment without reading source code. The docs should explain how to launch agents from modules or built-in aliases, how to pass runtime overrides, and what capabilities the packaged agents expose.

## Requirements

- Provide a dedicated page describing the `good-agent run` command, including argument formats (`module:path`), built-in aliases, runtime overrides (`--model`, `--temperature`), extra factory args, and interactive loop behavior (tool output, markdown rendering, commands like `exit`/`clear`).
- Document the built-in agents (`good-agent-agent`, `research-agent`) with their purposes, prompts, tool access, and external dependencies that users may need to install.
- Surface practical examples showing how to invoke each built-in agent via the CLI and as Python imports.
- Add navigation entries so both topics are discoverable from the main documentation site without digging through source.
- Keep tone consistent with existing docs: concise headings, callout blocks for warnings/dependencies, and short Python snippets where helpful.

## Implementation Notes

- Create `docs/cli/run.md` for the CLI guide; structure with sections for prerequisites, invocation syntax, configuration overrides, and interactive session tips.
- Add `docs/reference/built-in-agents.md` summarizing bundled agents, their prompts, tool lists, aliases, and optional dependency installation instructions.
- Use MkDocs Material admonitions (e.g. `!!! note`, `!!! warning`) for dependency callouts and best practices.
- Update `mkdocs.yml` navigation to add a "Command Line" group (or similar) for the CLI page and include the built-in agents page under Reference.
- Re-use code snippets from `src/good_agent/cli/run.py` and `src/good_agent/agents/` to keep documentation accurate; avoid duplicating long prompts verbatim—summarize intent instead.

## Todo List

- [x] Draft CLI documentation page with usage examples and interactive tips.
- [x] Draft built-in agents reference page covering purpose, tools, and dependencies.
- [x] Wire both pages into MkDocs navigation.
- [x] Run `uv run mkdocs build` (or equivalent) to ensure docs compile.

## Testing Strategy

- Execute `uv run mkdocs build` to validate navigation and page formatting.
- Optionally lint Markdown with existing tooling if available (none currently enforced).
