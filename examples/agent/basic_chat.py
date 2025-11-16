"""Contrast Agent.call() vs Agent.execute()."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent
from good_agent.mock import MockLanguageModel


async def main() -> None:
    mock_llm = MockLanguageModel({})
    agent = Agent(
        "You respond cheerfully and keep answers short.",
        language_model=mock_llm,
    )

    async with agent:
        reply = await agent.call("Say hi to the user.")
        print("call() ->", reply.content)

        async for message in agent.execute("Outline a short plan", max_iterations=2):
            print(f"execute() step: {message.role} -> {message.content}")


if __name__ == "__main__":
    asyncio.run(main())
