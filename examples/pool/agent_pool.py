"""Demonstrate routing work across multiple Agent instances with AgentPool."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent
from good_agent.pool import AgentPool

try:  # pragma: no cover
    from .._shared.mock_llm import ExampleLanguageModel, assistant_response
except ImportError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from _shared.mock_llm import ExampleLanguageModel, assistant_response  # type: ignore[no-redef]


async def create_agent(index: int) -> Agent:
    responses = [
        assistant_response(f"Helper #{index} response {slot}") for slot in range(1, 5)
    ]
    agent = Agent(
        language_model=ExampleLanguageModel(responses),
    )
    agent.append(f"You are helper #{index} who responds briefly.", role="system")
    await agent.initialize()
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
