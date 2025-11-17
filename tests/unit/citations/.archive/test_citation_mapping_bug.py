#!/usr/bin/env python3

import asyncio

from good_agent import Agent, AssistantMessage
from good_agent.extensions import CitationManager


async def test_citation_mapping_bug():
    """Test the specific scenario from the notebook where citations get mismatched."""

    # Create agent with CitationManager
    agent = Agent(
        "You are a research assistant.",
        extensions=[CitationManager()],
        model="gpt-4o-mini",
    )

    await agent.initialize()
    citation_manager = agent[CitationManager]

    print("=" * 80)
    print("TEST: Citation Mapping Bug from Notebook")
    print("=" * 80)
    print()

    # Simulate the notebook scenario:
    # 1. First establish some citations in the index (from ground truth or earlier messages)
    print("Step 1: Populate index with initial citations")
    agent.append("""Initial research sources:
    
    [1]: https://politico.com/article1.html
    [2]: https://latimes.com/news2.html
    [3]: https://sfchronicle.com/report3.html
    """)

    print("Index after initial population:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    # 2. Add more citations from search results or fetched content
    print("Step 2: Add more citations from search results")
    agent.append("""Additional sources found:
    
    [4]: https://example.com/new-source1.pdf
    [5]: https://research.org/new-source2.html
    [6]: https://news.com/new-source3.html
    """)

    print("Index after adding more citations:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    # 3. Now simulate an LLM response that references multiple different citations
    print("Step 3: LLM response with multiple citation references")
    llm_response = AssistantMessage("""Based on my analysis:
    
    - The first finding comes from [!CITE_1!]
    - Additional data from [!CITE_2!] supports this
    - However, [!CITE_3!] presents a different perspective
    - Recent updates in [!CITE_4!] are noteworthy
    - The report in [!CITE_5!] confirms the trend
    - Finally, [!CITE_6!] provides additional context
    """)

    agent.append(llm_response)
    msg = agent[-1]

    print("LLM Response content:")
    print(msg.content_parts[0].text)
    print()

    print("Message citations field:")
    if msg.citations:
        print(f"  Found {len(msg.citations)} citations:")
        for i, url in enumerate(msg.citations, 1):
            print(f"    [{i}]: {url}")
    else:
        print("  No citations populated")
    print()

    # 4. Test what happens when we add a new message with overlapping references
    print("Step 4: Another message with overlapping references")
    msg2 = AssistantMessage("""Further analysis shows:
    
    - Revisiting [!CITE_1!] for clarity
    - New information from [!CITE_7!] (should not exist)
    - Comparing [!CITE_3!] and [!CITE_5!]
    """)

    agent.append(msg2)
    msg2_result = agent[-1]

    print("Second message citations:")
    if msg2_result.citations:
        print(f"  Found {len(msg2_result.citations)} citations:")
        for i, url in enumerate(msg2_result.citations, 1):
            print(f"    [{i}]: {url}")
    else:
        print("  No citations populated")
    print()

    # 5. Check the global index state
    print("Final global index state:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    await agent.events.async_close()


if __name__ == "__main__":
    asyncio.run(test_citation_mapping_bug())
