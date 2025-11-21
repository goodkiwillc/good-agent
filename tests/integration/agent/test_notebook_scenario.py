#!/usr/bin/env python3

import pytest
from good_agent import Agent, AssistantMessage
from good_agent.content import RenderMode
from good_agent.extensions.citations import CitationManager


@pytest.mark.asyncio
async def test_notebook_citation_scenario():
    """Reproduce the notebook's citation issue."""

    print("=" * 80)
    print("NOTEBOOK SCENARIO: Multiple URLs mapping to [!CITE_1!]")
    print("=" * 80)
    print()

    # Create agent like in notebook
    agent = Agent(
        "Campaign analyst", extensions=[CitationManager()], model="gpt-4o-mini"
    )

    await agent.initialize()
    citation_manager = agent[CitationManager]

    # Step 1: Ground truth citations (like from project.mdxl)
    print("Step 1: Ground truth citations")
    print("-" * 40)
    agent.append("""
Ground truth sources:

[1]: https://politico.com/ground-truth-1.html
[2]: https://latimes.com/ground-truth-2.html
[3]: https://news.com/ground-truth-3.html
""")

    print("Index after ground truth:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    # Step 2: Simulate WebFetcher adding URLs to index
    # This is what happens when fetch_tool processes URLs
    print("Step 2: WebFetcher adds fetched URLs to index")
    print("-" * 40)

    fetched_urls = [
        "https://example.com/fetched-article-1.html",
        "https://example.com/fetched-article-2.html",
        "https://research.org/fetched-paper.pdf",
        "https://news.site/fetched-news.html",
    ]

    # WebFetcher would add these to the index
    fetched_indices = []
    for url in fetched_urls:
        idx = citation_manager.index.add(url)
        fetched_indices.append(idx)
        print(f"  Added {url} -> [{idx}]")

    print("\nIndex after WebFetcher additions:")
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    # Step 3: LLM generates response referencing the fetched content
    # The LLM sees the content with citations and generates references
    print("Step 3: LLM response referencing fetched content")
    print("-" * 40)

    # Simulate what the LLM would generate after processing fetched content
    llm_response = AssistantMessage(f"""Based on the fetched articles:

- Article at [!CITE_{fetched_indices[0]}!] discusses the main topic
- The research paper [!CITE_{fetched_indices[2]}!] provides evidence
- News from [!CITE_{fetched_indices[3]}!] confirms this
- Another source [!CITE_{fetched_indices[1]}!] adds context

Also referencing ground truth [!CITE_1!] and [!CITE_2!].
""")

    agent.append(llm_response)
    msg = agent[-1]

    print("LLM response:")
    print(msg.content_parts[0].text)
    print()

    print("Message citations field:")
    if msg.citations:
        for i, url in enumerate(msg.citations, 1):
            print(f"  [{i}]: {url}")
    print()

    # Step 4: Check how it renders for display
    print("Step 4: How it renders for display")
    print("-" * 40)
    display_content = msg.render(RenderMode.DISPLAY)
    print("Display rendering (first 300 chars):")
    print(display_content[:300])
    print()

    # Step 5: Another LLM message with different citations
    print("Step 5: Second LLM response")
    print("-" * 40)

    # Add more URLs (simulating another fetch batch)
    more_urls = ["https://another.com/article.html", "https://different.org/paper.pdf"]

    more_indices = []
    for url in more_urls:
        idx = citation_manager.index.add(url)
        more_indices.append(idx)

    llm_response2 = AssistantMessage(f"""Further analysis:

The new source [!CITE_{more_indices[0]}!] contradicts [!CITE_1!].
However, [!CITE_{more_indices[1]}!] supports [!CITE_2!].
""")

    agent.append(llm_response2)
    msg2 = agent[-1]

    print("Second LLM response citations:")
    if msg2.citations:
        for i, url in enumerate(msg2.citations, 1):
            print(f"  [{i}]: {url}")
    print()

    # Final check of global index
    print("Final global index state:")
    print("-" * 40)
    for idx, url in citation_manager.index.items():
        print(f"  [{idx}]: {url}")
    print()

    await agent.events.close()


# if __name__ == "__main__":
#     asyncio.run(test_notebook_citation_scenario())
