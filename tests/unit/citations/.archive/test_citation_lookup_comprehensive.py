#!/usr/bin/env python3
"""
Test citation lookup for both [!CITE_X!] (LLM format) and [X] (markdown) formats.
"""

import asyncio

from good_agent import Agent, AssistantMessage
from good_agent.extensions import CitationManager


async def test_citation_lookup_comprehensive():
    """Test citation lookup from global index for different formats."""

    # Create agent with CitationManager
    agent = Agent(
        "You are a research assistant.",
        extensions=[CitationManager()],
        model="gpt-4o-mini",
    )

    await agent.ready()
    citation_manager = agent[CitationManager]

    print("=" * 60)
    print("SETUP: Populate global index with citations")
    print("=" * 60)

    # Populate the global index
    agent.append("""Initial sources:
    
    [1]: https://example.com/source1.pdf
    [2]: https://example.com/source2.html
    [3]: https://example.com/source3.json
    """)

    print("Global index:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    # Test 1: LLM format [!CITE_X!]
    print("=" * 60)
    print("TEST 1: LLM format [!CITE_X!] (as LLM would return)")
    print("=" * 60)

    llm_response_1 = AssistantMessage(
        """Based on [!CITE_1!] and [!CITE_2!], we conclude:
        
        The data in [!CITE_1!] shows positive trends.
        Additional evidence from [!CITE_3!] confirms this."""
    )

    agent.append(llm_response_1)
    msg1 = agent[-1]

    print("Content (first 80 chars):", msg1.content_parts[0].text[:80])
    print("\nMessage citations field:")
    if msg1.citations:
        print("  ✅ Citations populated from global index:")
        for i, url in enumerate(msg1.citations, 1):
            print(f"     [{i}]: {url}")
    else:
        print("  ❌ No citations (BUG)")
    print()

    # Test 2: Markdown format [X]
    print("=" * 60)
    print("TEST 2: Markdown format [X] (for compatibility)")
    print("=" * 60)

    llm_response_2 = AssistantMessage(
        """According to [1] and recent findings [2]:
        
        - Point from source [1]
        - Data from [2] and [3]"""
    )

    agent.append(llm_response_2)
    msg2 = agent[-1]

    print("Content (first 80 chars):", msg2.content_parts[0].text[:80])
    print("\nMessage citations field:")
    if msg2.citations:
        print("  ✅ Citations populated from global index:")
        for i, url in enumerate(msg2.citations, 1):
            print(f"     [{i}]: {url}")
    else:
        print("  ❌ No citations (BUG)")
    print()

    # Test 3: Mixed references (some valid, some not in index)
    print("=" * 60)
    print("TEST 3: Mixed references (only [1] and [3] exist)")
    print("=" * 60)

    llm_response_3 = AssistantMessage(
        """References to [!CITE_1!], [!CITE_5!], and [!CITE_3!].
        Note: [!CITE_5!] doesn't exist in index."""
    )

    agent.append(llm_response_3)
    msg3 = agent[-1]

    print("Content (first 80 chars):", msg3.content_parts[0].text[:80])
    print("\nMessage citations field:")
    if msg3.citations:
        print("  ✅ Citations populated (only valid ones):")
        for i, url in enumerate(msg3.citations, 1):
            print(f"     [{i}]: {url}")
    else:
        print("  ❌ No citations (BUG)")
    print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("Global index still contains all original citations:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")

    await agent.async_close()


if __name__ == "__main__":
    asyncio.run(test_citation_lookup_comprehensive())
