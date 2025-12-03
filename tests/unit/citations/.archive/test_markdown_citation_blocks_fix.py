import pytest
from good_agent import Agent
from good_agent.content import RenderMode
from good_agent.extensions.citations import CitationManager


class TestMarkdownCitationBlocksFix:
    """Test suite for the markdown citation blocks fix."""

    @pytest.mark.asyncio
    async def test_reference_block_completely_removed(self):
        """Test that reference blocks are completely removed from content."""
        content = """
        Some content with citations [1] and [2].
        
        [1]: https://example.com
        [2]: https://other.com
        """

        citation_manager = CitationManager()
        agent = Agent("Test", extensions=[citation_manager])
        await agent.initialize()

        agent.append(content)

        message = agent.messages[-1]

        # Check citations were extracted
        assert len(message.citations) == 2
        assert "example.com" in str(message.citations[0])
        assert "other.com" in str(message.citations[1])

        # Display render should not contain reference blocks
        display = message.render(RenderMode.DISPLAY)
        assert "[1]: https://example.com" not in display
        assert "[2]: https://other.com" not in display

        # Should not have the problematic pattern
        assert "[!CITE_1!]: [!CITE_" not in display
        assert "[!CITE_2!]: [!CITE_" not in display

    @pytest.mark.asyncio
    async def test_reference_block_with_large_global_index(self):
        """Test reference blocks don't conflict with large global indices."""
        citation_manager = CitationManager()

        # Populate global index with many citations
        for i in range(200):
            citation_manager.index.add(f"https://prev.com/doc{i}.pdf")

        content = """
        Document with citations [1], [2], [3].
        
        [1]: https://new1.com
        [2]: https://new2.com  
        [3]: https://new3.com
        """

        agent = Agent("Test", extensions=[citation_manager])
        await agent.initialize()

        agent.append(content)

        message = agent.messages[-1]

        # Check display rendering
        display = message.render(RenderMode.DISPLAY)

        # Should not have the problematic double citation pattern
        import re

        problematic = re.compile(r"\[!CITE_\d+!\]:\s*\[!CITE_\d+!\]")
        assert not problematic.search(display), f"Found problematic pattern in: {display}"

        # Reference blocks should be completely removed
        assert "[1]: " not in display
        assert "[2]: " not in display
        assert "[3]: " not in display

    @pytest.mark.asyncio
    async def test_mixed_content_and_reference_blocks(self):
        """Test content mixed with reference blocks."""
        content = """
        # Document Title
        
        Some text with citation [1].
        
        More text here [2].
        
        [1]: https://source1.com
        [2]: https://source2.com
        
        Final paragraph with [3].
        
        [3]: https://source3.com
        """

        citation_manager = CitationManager()
        agent = Agent("Test", extensions=[citation_manager])
        await agent.initialize()

        agent.append(content)

        message = agent.messages[-1]

        # Citations should be extracted
        assert len(message.citations) == 3

        # LLM render should have normalized citations
        llm = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm
        assert "[!CITE_2!]" in llm
        assert "[!CITE_3!]" in llm

        # Reference blocks should be removed
        assert "[1]: https://source1.com" not in llm
        assert "[2]: https://source2.com" not in llm
        assert "[3]: https://source3.com" not in llm

    @pytest.mark.asyncio
    async def test_reference_block_with_angle_brackets(self):
        """Test reference blocks with URLs in angle brackets."""
        content = """
        Citations [1] and [2].
        
        [1]: <https://example.com/with/angle/brackets>
        [2]: https://normal.com
        """

        citation_manager = CitationManager()
        agent = Agent("Test", extensions=[citation_manager])
        await agent.initialize()

        agent.append(content)

        message = agent.messages[-1]

        # Both formats should be extracted
        assert len(message.citations) == 2
        assert "example.com/with/angle/brackets" in str(message.citations[0])
        assert "normal.com" in str(message.citations[1])

        # Display should not have reference blocks
        display = message.render(RenderMode.DISPLAY)
        assert "[1]: <https://example.com" not in display
        assert "[2]: https://normal.com" not in display

    @pytest.mark.asyncio
    async def test_empty_content_after_reference_removal(self):
        """Test when content is only reference blocks."""
        content = """
        [1]: https://only-refs.com
        [2]: https://nothing-else.com
        """

        citation_manager = CitationManager()
        agent = Agent("Test", extensions=[citation_manager])
        await agent.initialize()

        agent.append(content)

        message = agent.messages[-1]

        # Citations should still be extracted
        assert len(message.citations) == 2

        # Content should be empty or minimal after removal
        display = message.render(RenderMode.DISPLAY)
        # Should not contain the reference blocks
        assert "[1]: https://only-refs.com" not in display
        assert "[2]: https://nothing-else.com" not in display

    @pytest.mark.asyncio
    async def test_reference_blocks_not_treated_as_citations(self):
        """Test that the reference block format itself isn't treated as a citation."""
        content = """
        Text with [1] citation.
        
        [1]: https://example.com
        """

        citation_manager = CitationManager()
        agent = Agent("Test", extensions=[citation_manager])
        await agent.initialize()

        agent.append(content)

        message = agent.messages[-1]

        # Only one citation should be extracted (the URL, not the [1]: part)
        assert len(message.citations) == 1
        assert "example.com" in str(message.citations[0])

        # LLM render should have [!CITE_1!] but not [!CITE_1!]:
        llm = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm
        # The colon after citation should not appear
        assert "[!CITE_1!]:" not in llm
