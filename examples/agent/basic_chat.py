"""Contrast Agent.call() vs Agent.execute()."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent

try:  # pragma: no cover - fallback for ``python examples/...`` execution
    from .._shared.mock_llm import ExampleLanguageModel, assistant_response
except ImportError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from _shared.mock_llm import ExampleLanguageModel, assistant_response  # type: ignore[no-redef]


async def main() -> None:
    agent = Agent(
        language_model=ExampleLanguageModel(
            [
                assistant_response("Hi there!"),
                assistant_response("Step 1: gather facts."),
                assistant_response("Step 2: summarize the plan."),
            ]
        ),
    )
    agent.append("You respond cheerfully and keep answers short.", role="system")

    async with agent:
        reply = await agent.call("Say hi to the user.")
        print("call() ->", reply.content)

        async for message in agent.execute("Outline a short plan", max_iterations=2):
            print(f"execute() step: {message.role} -> {message.content}")


if __name__ == "__main__":
    asyncio.run(main())
