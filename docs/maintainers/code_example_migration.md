# Documentation Code Example Migration Guide

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

We are migrating inline Python code blocks from Markdown documentation into executable, tested Python files. This ensures our documentation examples remain valid, runnable, and up-to-date with the codebase.

## Status
- **Completed**: 
  - `docs/core/agents.md`
  - `docs/features/modes.md`
- **Remaining**: All other files in `docs/` (use `glob docs/**/*.md` to find them).

## Workflow

### 1. Select a File
Pick a markdown file from `docs/` that contains Python code blocks (e.g., `docs/core/tools.md`).

### 2. Extract the Example
Create a new Python file in `examples/docs/` with a descriptive name matching the source file and context.
*   **Naming Convention**: `{source_file}_{topic}.py` (e.g., `tools_basic.py`, `tools_dependencies.py`).

### 3. Structure the Example
The file **must** be standalone and executable. Follow this pattern:

```python
import asyncio
from good_agent import Agent

# ... definitions, classes, tools ...

async def main():
    # ... the logic from the example ...
    async with Agent("System") as agent:
        await agent.call("Hello")

if __name__ == "__main__":
    asyncio.run(main())
```

**Requirements:**
*   Wrap top-level logic in `async def main():`.
*   Ensure all imports are present.
*   Use `async with Agent(...)` context managers where possible for automatic cleanup.
*   If the example uses `print()`, ensure it still prints so the user sees expected output (assertions are good, but printing helps debug).

### 4. Update the Markdown
Replace the code block in the `.md` file with the snippet syntax:

**Old:**
\```python
print("Hello")
\```

**New:**
\```python
--8<-- "examples/docs/my_new_example.py"
\```

*Note: You can select specific lines if needed: `--8<-- "examples/docs/file.py:5:10"`*

### 5. Format and Validate
Run the formatter on your new file:

```bash
bash /Users/goodkiwi/.claude/skills/pyformat/scripts/format.sh examples/docs/your_new_file.py
```

### 6. Test
Run the documentation test runner. This auto-discovers files in `examples/docs/` and runs their `main()` function, recording interactions via VCR.

```bash
# Run all doc examples
uv run pytest tests/docs/test_examples.py -v

# Run specific example
uv run pytest tests/docs/test_examples.py -k "your_new_file.py" -v
```

## Common Gotchas & Fixes

| Issue | Solution |
|-------|----------|
| **`AttributeError: temporary_tools`** | Use `await agent.tools.register_tool(tool_func)` instead of context managers for tools. |
| **`AssertionError` in VCR** | Response content from LLMs varies. Relax assertions to check for key phrases or existence (`assert response.content`). |
| **Initialization Errors** | Ensure `await agent.initialize()` is called if not using `async with`. |
| **Context Access** | Use `agent.context.as_dict()` instead of private `_data`. |
| **AgentPool** | `AgentPool` is not a context manager. Use `await pool.get()` and `await pool.put()`. |
| **JSON Serialization** | `ULID` and `datetime` objects need explicit string conversion for JSON/Pydantic dumps. |

## Goal
100% of documentation code examples should be sourced from `examples/docs/` and passing in CI.
