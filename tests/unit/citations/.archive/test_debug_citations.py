#!/usr/bin/env python3

import asyncio
import sys

import pytest
from good_agent import Agent, AssistantMessage
from good_agent.extensions import CitationManager
from loguru import logger

# Enable debug logging
logger.remove()
logger.add(sys.stderr, level="DEBUG")


@pytest.mark.asyncio
async def test_debug_citations():
    """Debug test to trace citation processing."""

    # Create agent with CitationManager
    agent = Agent(
        "You are a research assistant.",
        extensions=[CitationManager()],
        model="gpt-4o-mini",
    )

    await agent.initialize()
    citation_manager = agent[CitationManager]

    print("=" * 60)
    print("STEP 1: Populate index")
    print("=" * 60)

    # Populate index
    agent.append("[1]: https://example.com/test.pdf")

    print(f"Index contents: {dict(citation_manager.index.items())}")
    print()

    print("=" * 60)
    print("STEP 2: LLM response with [!CITE_1!]")
    print("=" * 60)

    # Test LLM response - manually check what's happening
    test_content = "Based on [!CITE_1!], we see results."

    # Check if CitationPatterns can detect this
    from good_agent.extensions.citations.formats import (
        CitationPatterns,
    )

    detected_format = CitationPatterns.detect_format(test_content)
    print(f"Detected format: {detected_format}")

    has_llm = CitationPatterns.LLM_CITE.search(test_content)
    print(f"Has LLM pattern: {has_llm}")

    has_markdown = CitationPatterns.MARKDOWN.search(test_content)
    print(f"Has Markdown pattern: {has_markdown}")

    # Now create the message
    print("\nCreating AssistantMessage...")
    msg = AssistantMessage(test_content)
    agent.append(msg)

    result_msg = agent[-1]
    if hasattr(result_msg.content_parts[0], "text"):
        print(f"\nMessage content: {result_msg.content_parts[0].text}")
    print(f"Message citations: {result_msg.citations}")

    await agent.events.close()


if __name__ == "__main__":
    asyncio.run(test_debug_citations())
