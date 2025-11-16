"""Install CitationManager to normalize inline citations."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent
from good_agent.extensions.citations.manager import CitationManager
from good_agent.messages import AssistantMessage
from good_agent.mock import MockLanguageModel


async def main() -> None:
    citations = CitationManager()
    agent = Agent(
        "Normalize citations automatically.",
        language_model=MockLanguageModel({}),
        extensions=[citations],
    )

    async with agent:
        agent.append(
            AssistantMessage(
                content="According to the report [1], adoption is growing.",
                citations=["https://example.com/report"],
            )
        )

    print("indexed citations:", len(citations.index))


if __name__ == "__main__":
    asyncio.run(main())
