"""Demonstrate routing work across multiple Agent instances with AgentPool."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent
from good_agent.mock import MockLanguageModel
from good_agent.pool import AgentPool


async def create_agent(index: int) -> Agent:
    agent = Agent(
        f"You are helper #{index} who responds briefly.",
        language_model=MockLanguageModel({}),
    )
    await agent.ready()
    return agent


async def main() -> None:
    agents = [await create_agent(i) for i in range(2)]
    pool = AgentPool(agents)

    async def handle_request(idx: int) -> None:
        agent = pool[idx % len(pool)]
        response = await agent.call(f"request {idx}: say hi")
        print(f"worker {idx % len(pool)} -> {response.content}")

    await asyncio.gather(*(handle_request(i) for i in range(4)))


if __name__ == "__main__":
    asyncio.run(main())
