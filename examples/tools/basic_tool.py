"""Minimal tool registration and execution example."""

from __future__ import annotations

import asyncio

from good_agent.tools import ToolManager, tool


@tool(description="Search project documentation for a phrase")
async def search_docs(query: str) -> str:
    """Simple async function that behaves like an LLM tool."""

    return f"Pretend search results for: {query}"


async def main() -> None:
    manager = ToolManager()
    await manager.register_tool(search_docs, name="docs_search")

    response = await manager["docs_search"](query="event router priorities")
    print("Tool success:", response.success)
    print("Payload:", response.response)


if __name__ == "__main__":
    asyncio.run(main())
