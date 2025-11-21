# `good-agent run`

Launch any Good Agent straight from the terminal and chat with it interactively.

## Prerequisites

- Install `good-agent` with the CLI extras (`pip install good-agent[cli]`) to get Rich and Prompt Toolkit.
- Ensure your agent module is importable (current working directory or installed package).

!!! note "Command synopsis"
    ```bash
    good-agent run [OPTIONS] module.path:object_name [EXTRA_ARGS...]
    ```

## Loading agents

- **Direct instance**: point at a module-level variable.
  ```bash
  good-agent run examples.sales:agent
  ```
- **Factory function**: pass additional arguments after the path; they will be forwarded to the callable.
  ```bash
  good-agent run examples.factory:build_support_agent prod us-east
  ```

If the agent cannot be imported, the CLI prints the Python import error so you can fix module paths.

## Built-in aliases

The loader recognises shortcuts for the reference agents:

| Alias             | Loads |
| ----------------- | ----- |
| `good-agent`      | `good_agent.agents.meta:agent` |
<!-- | `good-agent-agent`| `good_agent.agents.meta:agent` | -->
| `research`        | `good_agent.agents.research:agent` |
| `research-agent`  | `good_agent.agents.research:agent` |

Use these when you want to explore the library without writing code first:

```bash
good-agent run good-agent
good-agent run research --model gpt-4o-mini
```

## Runtime overrides

You can temporarily override key configuration values without editing Python code:

```bash
good-agent run examples.sales:agent --model gpt-4o --temperature 0.1
```

The overrides update `Agent.config` before the session starts. Additional CLI options are ignored, so stick to the documented flags above.

## Passing factory arguments

Arguments placed after the agent path are forwarded verbatim to factory callables:

```bash
good-agent run examples.factory:build_support_agent prod us-east "level=enterprise"
```

- Values remain strings; cast them inside your factory if you need other types.
- Use shell quoting for values containing spaces.
- Extra options (those starting with `--`) are ignored unless your shell passes them as positional arguments.

If you provide extra arguments to an agent instance (rather than a callable), they are silently discarded.

## Interactive session controls

`good-agent run` shows every message from `Agent.execute()`:

- Assistant messages render as Markdown with Rich formatting.
- Tool calls show a cyan panel with the tool name and arguments before the tool runs.
- Tool outputs are wrapped in a blue panel; long payloads are truncated for readability.
- Note: streaming is not yet supported, so responses will appear only after the agent finishes processing.

Session shortcuts:

- Type `exit` or `quit` to leave.
- Type `clear` to wipe the terminal output.
- Press <kbd>Ctrl+C</kbd> to cancel the current prompt (the loop continues).
- Press <kbd>Ctrl+D</kbd> to end the process.

!!! tip "Re-running prompts"
    The prompt history remembers previous inputs. Use the up-arrow to repeat or tweak earlier questions.

!!! note "Persisting session history"
    The interactive shell uses an in-memory history. Export `PROMPT_TOOLKIT_HISTORY=~/.good-agent-history` before launching if you want entries saved between runs.

## Troubleshooting

- **"Invalid agent path"** – make sure the argument is `module:object`.
- **Import errors** – run the command from your project root or add the path with `PYTHONPATH`.
- **Missing dependencies** – built-in agents may require extra pip packages; see [Built-In Agents](../reference/built-in-agents.md).
