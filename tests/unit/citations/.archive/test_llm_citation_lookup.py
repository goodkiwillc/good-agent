#!/usr/bin/env python3

import asyncio

import pytest
from good_agent import Agent, AssistantMessage
from good_agent.extensions import CitationManager


@pytest.mark.asyncio
async def test_llm_citation_lookup():
    """Test that citation references from LLM should lookup URLs from global index."""

    # Create agent with CitationManager
    agent = Agent(
        "You are a research assistant.",
        extensions=[CitationManager()],
        model="gpt-4o-mini",
    )

    await agent.ready()
    citation_manager = agent[CitationManager]

    print("=" * 60)
    print("STEP 1: Populate global index with citations")
    print("=" * 60)

    # First, populate the global index with some citations
    # (simulating earlier messages that established citations)
    agent.append("""Initial research found these sources:
    
    [1]: https://example.com/source1.pdf
    [2]: https://example.com/source2.html
    [3]: https://example.com/source3.json
    """)

    print("Global index after first message:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    print("=" * 60)
    print("STEP 2: LLM response with citation references")
    print("=" * 60)

    # Now simulate an LLM response that references these citations
    # WITHOUT including the URLs (just the reference numbers)
    llm_response = AssistantMessage(
        """Based on the analysis [1] and the data from [2], we can conclude:
        
        1. The trend is positive according to [1]
        2. The statistics in [2] support this
        3. Additional evidence from [3] confirms our hypothesis
        
        The most important finding is in citation [1]."""
    )

    agent.append(llm_response)
    msg = agent[-1]

    print("LLM Response content:")
    print(f"  {msg.content_parts[0].text[:100]}...")
    print()

    print("Message citations field (SHOULD have URLs from global index):")
    if msg.citations:
        for i, url in enumerate(msg.citations, 1):
            print(f"  [{i}]: {url}")
    else:
        print("  ❌ No citations in message.citations field!")
        print(
            "  This is the bug - citations [1], [2], [3] should lookup URLs from global index"
        )
    print()

    print("Global index still has all citations:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    print("=" * 60)
    print("EXPECTED BEHAVIOR")
    print("=" * 60)
    print("""
    When an LLM response contains [1], [2], [3] references:
    1. CitationManager should detect these references
    2. Look up the URLs from the global index
    3. Populate message.citations with those URLs
    
    Currently: message.citations is None/empty
    Should be: message.citations = [url1, url2, url3] from global index
    """)

    await agent.events.async_close()


if __name__ == "__main__":
    asyncio.run(test_llm_citation_lookup())
