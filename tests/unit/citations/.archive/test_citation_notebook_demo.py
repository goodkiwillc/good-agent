#!/usr/bin/env python3

import asyncio

from good_agent import Agent
from good_agent.extensions import CitationManager


async def demo_citation_access():
    """Show how to access citations from messages and the CitationManager."""

    # Create agent with CitationManager
    agent = Agent(
        "You are a research assistant.",
        extensions=[CitationManager()],
        model="gpt-4o-mini",
    )

    await agent.initialize()

    # Simulate a response with citations (like from the campaign analysis)
    agent.append("""Based on recent news [1] and analysis [2], the California Governor race shows:
    
    - Katie Porter leads in polls [1]
    - Gavin Newsom's approval rating has changed [2]
    - New candidate announcements expected [3]
    
    [1]: https://politico.com/california-governor-2026
    [2]: https://latimes.com/newsom-approval-rating
    [3]: https://sfchronicle.com/candidate-announcements
    """)

    print("=" * 60)
    print("ACCESSING CITATIONS FROM MESSAGES")
    print("=" * 60)
    print()

    # Method 1: Access citations from the message directly
    message = agent[-1]
    print("Method 1: From message.citations field")
    print("-" * 40)
    if message.citations:
        for i, url in enumerate(message.citations, 1):
            print(f"  [{i}]: {url}")
    else:
        print("  No citations in message.citations field")
    print()

    # Method 2: Access from CitationManager's global index
    citation_manager = agent[CitationManager]
    print("Method 2: From CitationManager.index")
    print("-" * 40)
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    # Method 3: Get a formatted summary
    print("Method 3: CitationManager.get_citations_summary()")
    print("-" * 40)
    print(citation_manager.get_citations_summary())
    print()

    # Method 4: Export citations in different formats
    print("Method 4: Export citations")
    print("-" * 40)

    # JSON format
    import json

    citations_json = json.loads(citation_manager.export_citations("json"))
    print("JSON format (total citations):", citations_json["total_citations"])

    # Markdown format
    citations_md = citation_manager.export_citations("markdown")
    print("\nMarkdown format:")
    print(citations_md)

    # Method 5: Access citation metadata (if available)
    print("\nMethod 5: Citation metadata")
    print("-" * 40)
    for idx in citation_manager.index.as_dict().keys():
        metadata = citation_manager.index.get_metadata(idx)
        if metadata:
            print(f"  Citation [{idx}] metadata: {metadata}")
        else:
            print(f"  Citation [{idx}]: No metadata")

    await agent.events.async_close()
    print("\n✅ Demo completed")

    return agent, citation_manager


if __name__ == "__main__":
    agent, manager = asyncio.run(demo_citation_access())

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
The CitationManager correctly populates citations in two places:

1. message.citations - List of URLs for that specific message
2. CitationManager.index - Global index of all citations across all messages

To access citations in your notebook:
- For a specific message: message.citations
- For all citations: agent[CitationManager].index
- For formatted output: agent[CitationManager].get_citations_summary()
""")
