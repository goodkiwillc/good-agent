#!/usr/bin/env python3
"""Test script to verify how citations are displayed in different render modes."""

import pytest
from good_agent import Agent, AssistantMessage
from good_agent.content import RenderMode
from good_agent.extensions import CitationManager


@pytest.mark.asyncio
async def test_citation_display():
    """Test how citations are displayed in different contexts."""

    # Create agent with CitationManager
    agent = Agent(
        "You are a helpful assistant",
        extensions=[CitationManager()],
        model="gpt-4o-mini",
    )

    await agent.ready()

    # Simulate what happens in a real conversation
    # 1. Add a message with citations like an LLM would
    assistant_msg = AssistantMessage(
        """Based on the analysis [1] and recent research [2], we can see that:

1. The data shows improvement [1]
2. The trends are positive [2]
3. Further studies confirm this [3]""",
        citations=[
            "https://example.com/analysis.pdf",
            "https://research.org/paper.pdf",
            "https://studies.edu/confirmation.html",
        ],
    )

    agent.append(assistant_msg)
    msg = agent[-1]

    print("=" * 60)
    print("ASSISTANT MESSAGE WITH CITATIONS")
    print("=" * 60)
    print()

    print("1. Message citations field:")
    print(f"   {msg.citations}")
    print()

    print("2. Raw content (from content_parts[0].text):")
    print(f"   {msg.content_parts[0].text[:100]}...")
    print()

    print("3. Rendered for DISPLAY mode:")
    display_content = msg.render(RenderMode.DISPLAY)
    print(f"   {display_content[:200]}...")
    print()

    print("4. Rendered for LLM mode:")
    llm_content = msg.render(RenderMode.LLM)
    print(f"   {llm_content[:200]}...")
    print()

    print("5. CitationManager index:")
    citation_manager = agent[CitationManager]
    print(f"   Total citations: {citation_manager.get_citations_count()}")
    for idx, url in citation_manager.index.items():
        print(f"   [{idx}]: {url}")
    print()

    print("6. Citation summary from manager:")
    print(citation_manager.get_citations_summary())
    print()

    # Test what happens when we add another message that references citations
    agent.append("I'd like to know more about the findings in citation [2]")
    msg2 = agent[-1]

    print("=" * 60)
    print("USER MESSAGE REFERENCING CITATIONS")
    print("=" * 60)
    print()
    print(f"Raw content: {msg2.content_parts[0].text}")
    print(f"Citations field: {msg2.citations}")
    print()

    await agent.async_close()
    print("✅ Test completed")
