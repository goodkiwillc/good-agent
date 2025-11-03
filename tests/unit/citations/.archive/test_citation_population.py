#!/usr/bin/env python3
"""Test script to verify citation population in messages."""

import asyncio

from good_agent import Agent, AssistantMessage
from good_agent.extensions import CitationManager


async def test_citation_population():
    """Test that citations are properly populated in messages."""

    # Create agent with CitationManager
    agent = Agent(
        "You are a helpful assistant",
        extensions=[CitationManager()],
        model="gpt-4o-mini",
    )

    await agent.ready()

    # Test 1: Direct message with citations in content
    print("Test 1: Message with inline citations")
    agent.append("According to the source [1], the data shows improvement.")
    msg1 = agent[-1]
    print(f"  Content: {msg1.content_parts[0].text[:50]}...")
    print(f"  Citations field: {msg1.citations}")
    print()

    # Test 2: Message with markdown reference
    print("Test 2: Message with markdown references")
    agent.append("""
The research [1] shows interesting results.

[1]: https://example.com/research.pdf
""")
    msg2 = agent[-1]
    print(f"  Content (first 50 chars): {msg2.content_parts[0].text[:50]}...")
    print(f"  Citations field: {msg2.citations}")
    print()

    # Test 3: Assistant message with citations
    print("Test 3: Assistant message creation with citations")
    assistant_msg = AssistantMessage(
        "Based on the research [1], we can conclude that...",
        citations=["https://example.com/paper.pdf"],
    )
    agent.append(assistant_msg)
    msg3 = agent[-1]
    print(f"  Content: {msg3.content_parts[0].text[:50]}...")
    print(f"  Citations field: {msg3.citations}")
    print()

    # Test 4: Check CitationManager index
    print("Test 4: CitationManager global index")
    citation_manager = agent[CitationManager]
    print(f"  Total citations in index: {citation_manager.get_citations_count()}")
    print(f"  Index contents: {dict(citation_manager.index.items())}")
    print()

    # Test 5: Message with inline URLs that should become citations
    print("Test 5: Message with inline URLs")
    agent.append(
        "Check out this article at https://news.example.com/article and this paper https://research.org/paper.pdf"
    )
    msg5 = agent[-1]
    print(f"  Original content (first 50 chars): {msg5.content_parts[0].text[:50]}...")
    print(f"  Citations field: {msg5.citations}")
    print(
        f"  Transformed content has [!CITE_X!]: {'[!CITE_' in msg5.content_parts[0].text}"
    )
    print()

    await agent.async_close()
    print("✅ Test completed")


if __name__ == "__main__":
    asyncio.run(test_citation_population())
