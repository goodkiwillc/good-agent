<p align="center">
  <img src="assets/logo.svg" width="180" alt="Good Agent Logo">
</p>

# A Good Agent

Composable agent orchestration toolkit with a deliberately small public API
surface (30 entries) and batteries-included examples.

## Quick start

```python
import asyncio

from good_agent.agent import Agent


async def main() -> None:
    agent = Agent()
    agent.append("You respond cheerfully and keep answers short.", role="system")

    async with agent:
        reply = await agent.call("Say hi to the user.")
        print("call() ->", reply.content)

        async for step in agent.execute("Outline a short plan", max_iterations=2):
            print(step.role, step.content)


if __name__ == "__main__":
    asyncio.run(main())
```

Need an offline workflow? Wrap your calls with ``agent.mock(...)`` (see
``examples/agent/basic_chat.py``) to queue deterministic responses without
hitting a live LLM provider.

Explore the runnable samples under `examples/` for tools, context managers, event
tracing, template rendering, and pool orchestration. The `tests/test_examples.py`
smoke suite executes every example to ensure they stay warning-free.

## Key docs

- [`docs/api-reference.md`](docs/api-reference.md) &mdash; single-page reference for
  the 30 allowed `Agent` attributes/facades.
- [`MIGRATION.md`](MIGRATION.md) &mdash; end-to-end replacement guide for deprecated
  helper methods (e.g., `ready()` → `initialize()`, `add_tool_invocation()` →
  `agent.tool_calls.record_invocation()`).
