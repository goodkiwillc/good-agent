import pytest
from good_agent import Agent
from good_agent.extensions.citations import CitationManager
from goodintel_core.types import URL


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Reference block filtering not fully implemented")
async def test_processed_reference_block_filtering():
    """Test that CitationManager filters out already-processed reference blocks."""

    # Create agent with CitationManager
    citation_manager = CitationManager()

    async with Agent(
        "Test agent",
        extensions=[citation_manager]
    ) as agent:
        # Content with confused reference blocks
        content_with_confused_refs = """
Here is some content with proper citations [!CITE_1!] and [!CITE_2!].

[!CITE_18!]: [!CITE_87!]

More content after the confused reference block.

[!CITE_5!]: [!CITE_22!]

Final content with another citation [!CITE_3!].
"""

        # Append content as assistant message (simulating LLM response with citations)
        citations = [
            URL("https://example1.com"),
            URL("https://example2.com"),
            URL("https://example3.com"),
        ]

        agent.append(
            "assistant",
            content_with_confused_refs.strip(),
            citations=citations
        )

        # Render for user display (this should filter out reference blocks)
        from good_agent.content import RenderMode

        user_content = agent.messages[-1].render(RenderMode.DISPLAY)

        # Verify that confused reference blocks are removed
        assert "[!CITE_18!]: [!CITE_87!]" not in user_content
        assert "[!CITE_5!]: [!CITE_22!]" not in user_content

        # But proper citations should remain (they get converted to markdown links)
        assert "[!CITE_1!]" not in user_content  # Should be converted to markdown link
        assert "[!CITE_2!]" not in user_content  # Should be converted to markdown link
        assert "[!CITE_3!]" not in user_content  # Should be converted to markdown link

        # Should contain the actual content
        assert "Here is some content" in user_content
        assert "More content after the confused reference block" in user_content
        assert "Final content with another citation" in user_content

        # Should have markdown links instead
        assert "[example1.com]" in user_content
        assert "[example2.com]" in user_content
        assert "[example3.com]" in user_content


@pytest.mark.asyncio
async def test_markdown_reference_block_filtering():
    """Test that CitationManager filters out markdown reference blocks."""

    citation_manager = CitationManager()

    async with Agent(
        "Test agent",
        extensions=[citation_manager]
    ) as agent:
        # Content with markdown reference blocks
        content_with_ref_blocks = """
Here is some content with citations [1] and [2].

[1]: https://example.com
[2]: https://other.com

More content here.
"""

        agent.append("user", content_with_ref_blocks.strip())

        # Render for display
        from good_agent.content import RenderMode

        user_content = agent.messages[-1].render(RenderMode.DISPLAY)

        # Reference blocks should be removed
        assert "[1]: https://example.com" not in user_content
        assert "[2]: https://other.com" not in user_content

        # Content should remain with citations converted
        assert "Here is some content" in user_content
        assert "More content here" in user_content


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Reference block filtering not fully implemented")
async def test_mixed_reference_block_filtering():
    """Test filtering of both markdown and processed reference blocks."""

    citation_manager = CitationManager()

    async with Agent(
        "Test agent",
        extensions=[citation_manager]
    ) as agent:
        # Content with both types of reference blocks
        mixed_content = """
Content with regular citations [!CITE_1!] and [2].

[1]: https://example.com
[2]: https://other.com

[!CITE_18!]: [!CITE_87!]

More content.

[!CITE_5!]: [!CITE_22!]
"""

        citations = [URL("https://example1.com")]

        agent.append(
            "assistant",
            mixed_content.strip(),
            citations=citations
        )

        # Render for display
        from good_agent.content import RenderMode

        user_content = agent.messages[-1].render(RenderMode.DISPLAY)

        # All reference blocks should be removed
        assert "[1]: https://example.com" not in user_content
        assert "[2]: https://other.com" not in user_content
        assert "[!CITE_18!]: [!CITE_87!]" not in user_content
        assert "[!CITE_5!]: [!CITE_22!]" not in user_content

        # Main content should remain
        assert "Content with regular citations" in user_content
        assert "More content" in user_content


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        await test_processed_reference_block_filtering()
        await test_markdown_reference_block_filtering()
        await test_mixed_reference_block_filtering()
        print("All tests passed!")

    asyncio.run(run_tests())
