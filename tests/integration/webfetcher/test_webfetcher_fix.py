#!/usr/bin/env python
"""Test script to verify WebFetcher tools return proper strings."""

import asyncio

from good_agent import Agent
from good_agent.extensions import CitationManager, WebFetcher


async def main():
    print("Testing WebFetcher tool output formatting\n")
    print("=" * 50)

    # Create agent with WebFetcher
    agent = Agent(
        "You are a helpful assistant.",
        extensions=[
            WebFetcher(
                default_ttl=3600,
                enable_summarization=True,
                summarization_model="gpt-4o-mini",
            ),
            CitationManager(),
        ],
        print_messages=True,
        print_messages_mode="llm",  # This is where we see tool outputs
    )

    await agent.ready()

    # Test fetch_url tool
    print("\n1. Testing fetch_url tool:")
    print("-" * 30)

    result = await agent.tools["fetch_url"](
        _agent=agent, url="https://example.com", ttl=3600
    )

    print(f"Tool returned type: {type(result.response)}")
    print(f"Success: {result.success}")
    if result.success:
        print("\nFormatted output:")
        print(result.response)

    # Test fetch_and_summarize tool
    print("\n\n2. Testing fetch_and_summarize tool:")
    print("-" * 30)

    result = await agent.tools["fetch_and_summarize"](
        _agent=agent,
        url="https://example.com",
        strategy="tldr",
        word_limit=50,
        ttl=3600,
    )

    print(f"Tool returned type: {type(result.response)}")
    print(f"Success: {result.success}")
    if result.success:
        print("\nFormatted output:")
        print(result.response)

    print("\n" + "=" * 50)
    print(
        "Test complete! Tools should now return formatted strings instead of dictionaries."
    )


if __name__ == "__main__":
    asyncio.run(main())
