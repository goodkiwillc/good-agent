#!/usr/bin/env python3

import asyncio

from good_agent import Agent, AssistantMessage
from good_agent.content import RenderMode
from good_agent.extensions import CitationManager


async def test_all_citation_scenarios():
    """Test all citation resolution scenarios comprehensively."""

    print("=" * 80)
    print("COMPREHENSIVE CITATION RESOLUTION TEST")
    print("=" * 80)
    print()

    # Test 1: Basic citation extraction from markdown references
    print("TEST 1: Markdown reference extraction")
    print("-" * 40)
    agent1 = Agent("Test", extensions=[CitationManager()])
    await agent1.ready()

    agent1.append("""
    Here's some content [1] with citations [2].
    
    [1]: https://example.com/one.pdf
    [2]: https://example.com/two.pdf
    """)

    msg1 = agent1[-1]
    cm1 = agent1[CitationManager]

    print(f"Message citations: {msg1.citations}")
    print(f"Global index: {dict(cm1.index.items())}")
    print(f"Content transformed: {'[!CITE_' in msg1.content_parts[0].text}")
    print()
    await agent1.async_close()

    # Test 2: Citation preservation when order is jumbled
    print("TEST 2: Non-sequential citation ordering")
    print("-" * 40)
    agent2 = Agent("Test", extensions=[CitationManager()])
    await agent2.ready()

    agent2.append("""
    References in weird order:
    
    [3]: https://example.com/three.pdf
    [1]: https://example.com/one.pdf
    [2]: https://example.com/two.pdf
    """)

    msg2 = agent2[-1]
    cm2 = agent2[CitationManager]

    print(f"Message citations: {msg2.citations}")
    print(f"Global index: {dict(cm2.index.items())}")

    # Now test referencing these
    agent2.append(
        AssistantMessage("Referring to [!CITE_1!], [!CITE_2!], and [!CITE_3!]")
    )
    msg2b = agent2[-1]
    print(f"Referenced citations: {msg2b.citations}")
    print()
    await agent2.async_close()

    # Test 3: Mixed citation formats in same message
    print("TEST 3: Mixed citation formats")
    print("-" * 40)
    agent3 = Agent("Test", extensions=[CitationManager()])
    await agent3.ready()

    # First establish some citations
    agent3.append("[1]: https://source1.com")

    # Now mix formats
    agent3.append("""
    Some inline URLs: https://inline1.com and https://inline2.com
    Plus a reference [1] and new reference:
    [2]: https://source2.com
    """)

    msg3 = agent3[-1]
    cm3 = agent3[CitationManager]

    print(f"Message citations: {msg3.citations}")
    print(f"Global index: {dict(cm3.index.items())}")
    print()
    await agent3.async_close()

    # Test 4: Citation lookup from pre-populated index
    print("TEST 4: Citation lookup from existing index")
    print("-" * 40)
    agent4 = Agent("Test", extensions=[CitationManager()])
    await agent4.ready()
    cm4 = agent4[CitationManager]

    # Pre-populate index
    agent4.append("""
    [1]: https://first.com
    [2]: https://second.com
    [3]: https://third.com
    """)

    print(f"Pre-populated index: {dict(cm4.index.items())}")

    # Now append message with references
    agent4.append(AssistantMessage("Analysis of [!CITE_2!] and [!CITE_3!]"))
    msg4 = agent4[-1]

    print(f"Looked up citations: {msg4.citations}")
    print()
    await agent4.async_close()

    # Test 5: Citation rendering in different modes
    print("TEST 5: Citation rendering modes")
    print("-" * 40)
    agent5 = Agent("Test", extensions=[CitationManager()])
    await agent5.ready()

    # Create message with citations
    msg5 = AssistantMessage(
        "Check [1] and [2]", citations=["https://url1.com", "https://url2.com"]
    )
    agent5.append(msg5)
    final_msg = agent5[-1]

    print(f"Original content: {final_msg.content_parts[0].text}")
    print(f"Citations field: {final_msg.citations}")
    print(f"Rendered for LLM: {final_msg.render(RenderMode.LLM)[:50]}...")
    print(f"Rendered for DISPLAY: {final_msg.render(RenderMode.DISPLAY)[:50]}...")
    print()
    await agent5.async_close()

    # Test 6: WebFetcher-like scenario (adding citations from tools)
    print("TEST 6: Tool-added citations scenario")
    print("-" * 40)
    agent6 = Agent("Test", extensions=[CitationManager()])
    await agent6.ready()
    cm6 = agent6[CitationManager]

    # Simulate tool adding citations to index
    idx1 = cm6.index.add("https://fetched1.com")
    idx2 = cm6.index.add("https://fetched2.com")
    idx3 = cm6.index.add("https://fetched3.com")

    print(f"Tool-populated index: {dict(cm6.index.items())}")

    # LLM references these
    agent6.append(AssistantMessage(f"Based on [!CITE_{idx1}!] and [!CITE_{idx3}!]"))
    msg6 = agent6[-1]

    print(f"Tool citation lookup: {msg6.citations}")
    print()
    await agent6.async_close()

    # Test 7: Citation index order preservation
    print("TEST 7: Index order preservation")
    print("-" * 40)
    agent7 = Agent("Test", extensions=[CitationManager()])
    await agent7.ready()
    cm7 = agent7[CitationManager]

    # Add citations in specific order
    urls = ["https://a.com", "https://b.com", "https://c.com", "https://d.com"]

    indices = []
    for url in urls:
        idx = cm7.index.add(url)
        indices.append(idx)
        print(f"Added {url} -> index {idx}")

    print(f"Final index: {dict(cm7.index.items())}")
    print(f"Indices returned: {indices}")

    # Verify lookup
    for idx in indices:
        url = cm7.index[idx]
        print(f"Index {idx} -> {url}")
    print()
    await agent7.async_close()

    print("=" * 80)
    print("ALL TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_all_citation_scenarios())
