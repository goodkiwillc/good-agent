import asyncio

import pytest
from good_agent import Agent, tool
from good_agent.content import RenderMode
from good_agent.core.types import URL
from good_agent.extensions import CitationManager


class TestCitationReferenceBlockProcessing:
    """Test the specific issue with markdown reference blocks containing citation references."""

    @pytest.mark.asyncio
    async def test_ground_truth_with_citations(self):
        """Test processing ground truth documents with markdown reference blocks and citation references."""
        # This is the exact pattern from the campaign analyst notebook
        ground_truth_text = """This is ground truth content with citations.

According to the report [!CITE_1!], the findings are significant.
Another source [!CITE_2!] confirms this.

[1]: https://example.com/report1
[2]: https://example.com/report2
"""

        @tool
        async def get_ground_truth() -> str:
            """Get the ground truth document with citations"""
            return ground_truth_text

        agent = Agent(
            "You are a test agent",
            extensions=[CitationManager()],
            tools=[get_ground_truth],
        )
        await agent.ready()

        # Call the tool
        result = await agent.tool_calls.invoke(get_ground_truth)

        # Verify tool response is correct
        assert result.success
        assert result.response == ground_truth_text

        # Check that citations were extracted
        citation_manager = agent[CitationManager]
        assert len(citation_manager.index) == 2
        assert URL("https://example.com/report1") in citation_manager.index
        assert URL("https://example.com/report2") in citation_manager.index

        # Check the tool message
        tool_message = agent.messages[-1]
        assert tool_message.role == "tool"
        assert hasattr(tool_message, "citations")
        assert len(tool_message.citations) == 2

        # Verify LLM rendering preserves [!CITE_X!] format with global indices
        llm_content = tool_message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content
        assert (
            "[1]: https://example.com/report1" not in llm_content
        )  # Reference block should be removed

        # Verify display rendering converts to markdown links
        display_content = tool_message.render(RenderMode.DISPLAY)
        assert "[example.com](https://example.com/report1)" in display_content
        assert "[example.com](https://example.com/report2)" in display_content
        assert "[!CITE_1!]" not in display_content  # Should be converted to links


class TestCitationFormatRoundTrips:
    """Test round-trip transformations between all citation formats."""

    @pytest.mark.asyncio
    async def test_markdown_to_llm_and_back(self):
        """Test markdown citations can be converted to LLM format and back."""
        agent = Agent("Test", extensions=[CitationManager()])
        await agent.ready()

        # Start with markdown citations
        content = "Research [1] shows that [2] confirms the hypothesis."
        citations = [
            URL("https://research.org/paper"),
            URL("https://confirmation.edu/study"),
        ]

        agent.append(content, citations=citations)
        message = agent.messages[-1]

        # LLM format should use [!CITE_X!]
        llm_content = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content
        assert "[1]" not in llm_content
        assert "[2]" not in llm_content

        # Display format should use markdown links
        display_content = message.render(RenderMode.DISPLAY)
        assert "research.org" in display_content
        assert "confirmation.edu" in display_content

    @pytest.mark.asyncio
    async def test_xml_url_to_idx_transformation(self):
        """Test XML URLs are converted to idx attributes."""
        agent = Agent("Test", extensions=[CitationManager()])
        await agent.ready()

        # Tool response with XML URLs
        xml_content = """
        <results>
            <item url="https://first.com/page">First</item>
            <item url="https://second.org/article">Second</item>
        </results>
        """

        agent.append(xml_content, role="tool")
        message = agent.messages[-1]

        # Should extract citations
        citation_manager = agent[CitationManager]
        assert len(citation_manager.index) == 2

        # Display rendering should show URL attributes
        display_content = message.render(RenderMode.DISPLAY)
        assert 'url="https://first.com/page"' in display_content
        assert 'url="https://second.org/article"' in display_content

        # LLM rendering should also use idx
        llm_content = message.render(RenderMode.LLM)
        assert 'idx="1"' in llm_content or 'idx="2"' in llm_content

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Citation display rendering not fully implemented")
    async def test_inline_urls_extraction(self):
        """Test inline URLs are extracted and converted to citations."""
        agent = Agent("Test", extensions=[CitationManager()])
        await agent.ready()

        # Content with inline URLs
        content = "Check https://example.com for details and https://docs.org for documentation."

        agent.append(content)
        message = agent.messages[-1]

        # Should extract URLs as citations
        citation_manager = agent[CitationManager]
        assert len(citation_manager.index) == 2

        # LLM format should use citations
        llm_content = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content
        assert "https://example.com" not in llm_content

        # Display format should use markdown links (URLs may have trailing slashes)
        display_content = message.render(RenderMode.DISPLAY)
        assert (
            "[example.com](https://example.com" in display_content
        )  # May have trailing /
        assert "[docs.org](https://docs.org" in display_content  # May have trailing /


class TestMixedCitationFormats:
    """Test handling of mixed citation formats in the same content."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Citation display rendering not fully implemented")
    async def test_markdown_refs_with_inline_citations(self):
        """Test content with both markdown reference blocks and inline citations."""
        agent = Agent("Test", extensions=[CitationManager()])
        await agent.ready()

        # Complex content with multiple citation styles
        content = """Research shows [1] that the findings are significant.

Additionally, see [2] for more context.

[1]: https://research.org/paper1
[2]: https://study.edu/paper2
"""

        agent.append(content)
        message = agent.messages[-1]

        # Should extract both citations
        citation_manager = agent[CitationManager]
        assert len(citation_manager.index) == 2

        # Check citations are properly indexed
        assert URL("https://research.org/paper1") in citation_manager.index
        assert URL("https://study.edu/paper2") in citation_manager.index

        # LLM rendering should normalize to [!CITE_X!]
        llm_content = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content
        assert "[1]: https://research.org/paper1" not in llm_content

        # Display rendering should use markdown links
        display_content = message.render(RenderMode.DISPLAY)
        assert "[research.org](https://research.org/paper1)" in display_content
        assert "[study.edu](https://study.edu/paper2)" in display_content

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Citation display rendering not fully implemented")
    async def test_llm_citations_with_new_urls(self):
        """Test LLM-format citations mixed with new inline URLs."""
        agent = Agent("Test", extensions=[CitationManager()])
        await agent.ready()

        # First add some citations to the index
        agent.append("Initial source https://initial.com")

        # Now add content with LLM citations and new URL
        content = "Based on [!CITE_1!], we found https://newsource.org confirms this."
        agent.append(content, role="assistant")

        # Should have both citations
        citation_manager = agent[CitationManager]
        assert len(citation_manager.index) == 2

        # Check the assistant message
        assistant_msg = agent.messages[-1]

        # LLM rendering should have both citations normalized
        llm_content = assistant_msg.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content

        # Display should show proper links
        display_content = assistant_msg.render(RenderMode.DISPLAY)
        assert "initial.com" in display_content or "newsource.org" in display_content


class TestCitationConsistency:
    """Test citation consistency across multiple messages and render modes."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Citation index persistence not fully implemented")
    async def test_citation_index_persistence(self):
        """Test that citation indices remain consistent across messages."""
        agent = Agent("Test", extensions=[CitationManager()])
        await agent.ready()

        # Add citations across multiple messages
        agent.append("First source: https://first.com")
        agent.append("Second source: https://second.org", role="assistant")
        agent.append("Refer to [!CITE_1!] and https://third.net")

        citation_manager = agent[CitationManager]

        # Should have three unique citations
        assert len(citation_manager.index) == 3

        # Verify index consistency
        first_idx = citation_manager.index.lookup(URL("https://first.com"))
        second_idx = citation_manager.index.lookup(URL("https://second.org"))
        third_idx = citation_manager.index.lookup(URL("https://third.net"))

        assert first_idx == 1
        assert second_idx == 2
        assert third_idx == 3

        # Last message should reference correct indices
        last_msg = agent.messages[-1]
        llm_content = last_msg.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content  # Reference to first.com
        assert "[!CITE_3!]" in llm_content  # Reference to third.net

    @pytest.mark.asyncio
    async def test_duplicate_url_handling(self):
        """Test that duplicate URLs map to the same citation index."""
        agent = Agent("Test", extensions=[CitationManager()])
        await agent.ready()

        # Add same URL multiple times
        agent.append("First mention: https://example.com")
        agent.append("Second mention: https://example.com", role="assistant")
        agent.append("Also see https://example.com and https://other.org")

        citation_manager = agent[CitationManager]

        # Should only have 2 unique citations
        assert len(citation_manager.index) == 2

        # example.com should always be index 1
        example_idx = citation_manager.index.lookup(URL("https://example.com"))
        other_idx = citation_manager.index.lookup(URL("https://other.org"))

        assert example_idx == 1
        assert other_idx == 2


@pytest.mark.skip(reason="Manual test runner, not a unit test")
@pytest.mark.asyncio
async def test_main():
    """Run all tests manually."""
    print("Testing citation reference block processing...")
    test_ref_blocks = TestCitationReferenceBlockProcessing()
    await test_ref_blocks.test_ground_truth_with_citations()
    print("✓ Reference block test passed")

    print("\nTesting format round trips...")
    test_round_trips = TestCitationFormatRoundTrips()
    await test_round_trips.test_markdown_to_llm_and_back()
    await test_round_trips.test_xml_url_to_idx_transformation()
    await test_round_trips.test_inline_urls_extraction()
    print("✓ Round trip tests passed")

    print("\nTesting mixed formats...")
    test_mixed = TestMixedCitationFormats()
    await test_mixed.test_markdown_refs_with_inline_citations()
    await test_mixed.test_llm_citations_with_new_urls()
    print("✓ Mixed format tests passed")

    print("\nTesting consistency...")
    test_consistency = TestCitationConsistency()
    await test_consistency.test_citation_index_persistence()
    await test_consistency.test_duplicate_url_handling()
    print("✓ Consistency tests passed")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    # Run the tests
    asyncio.run(test_main())
