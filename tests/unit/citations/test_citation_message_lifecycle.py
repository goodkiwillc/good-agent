import pytest
from good_agent import Agent
from good_agent.content import RenderMode
from good_agent.extensions.citations import CitationManager


class TestMessageCreationWithCitations:
    """Test citation extraction during message creation."""

    @pytest.mark.asyncio
    async def test_create_message_with_markdown_citations(self):
        """Messages with markdown citations are extracted during creation."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        Research shows [1] that citations work.

        [1]: https://example.com/study.pdf
        """

        agent.append(content)
        message = agent.messages[-1]

        # Message should have local citations
        assert message.citations is not None
        assert len(message.citations) == 1
        assert str(message.citations[0]) == "https://example.com/study.pdf"

        # Content should be normalized to [!CITE_X!] format
        rendered = message.render(RenderMode.DISPLAY)
        assert "[1]:" not in rendered  # Reference block removed

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_create_message_with_explicit_citations_list(self):
        """Messages can be created with explicit citations parameter."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = "Research shows [1] and [2]."
        citations = [
            "https://example.com/study1.pdf",
            "https://example.com/study2.pdf",
        ]

        agent.append(content, citations=citations)
        message = agent.messages[-1]

        assert message.citations == citations
        assert len(message.citations) == 2

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_create_message_with_inline_urls(self):
        """Inline URLs are extracted as citations."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = "See https://example.com/doc.pdf for details."

        agent.append(content)
        message = agent.messages[-1]

        # URL should be extracted and added to citations
        assert message.citations is not None
        assert len(message.citations) >= 1
        assert any("example.com/doc.pdf" in str(c) for c in message.citations)

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_create_tool_message_with_xml_urls(self):
        """Tool messages with XML url attributes are extracted."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        <results>
            <item url="https://example.com/item1" />
            <item url="https://example.com/item2" />
        </results>
        """

        agent.append(content, role="tool")
        message = agent.messages[-1]

        # URLs should be extracted from XML
        assert message.citations is not None
        assert len(message.citations) == 2

        # Content should have idx attributes
        rendered = message.render(RenderMode.DISPLAY)
        assert 'idx="1"' in rendered or 'url="https://example.com/item1"' in rendered

        await agent.async_close()


class TestLocalCitationStorage:
    """Test that messages store citations with sequential local indices."""

    @pytest.mark.asyncio
    async def test_message_citations_are_sequential(self):
        """Message citations are stored as sequential list (1-based when referenced)."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        References [1], [3], and [5].

        [1]: https://example.com/doc1
        [3]: https://example.com/doc3
        [5]: https://example.com/doc5
        """

        agent.append(content)
        message = agent.messages[-1]

        # Sparse indices should be compacted to sequential
        assert len(message.citations) == 3
        assert str(message.citations[0]) == "https://example.com/doc1"
        assert str(message.citations[1]) == "https://example.com/doc3"
        assert str(message.citations[2]) == "https://example.com/doc5"

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_duplicate_urls_deduplicated_in_message(self):
        """Duplicate URLs within a message are deduplicated."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        First reference [1] and second reference [1] again.

        [1]: https://example.com/doc
        """

        agent.append(content)
        message = agent.messages[-1]

        # Only one citation despite multiple references
        assert len(message.citations) == 1
        assert str(message.citations[0]) == "https://example.com/doc"

        await agent.async_close()


class TestMessageRenderingForDisplay:
    """Test message rendering for user display."""

    @pytest.mark.asyncio
    async def test_render_display_converts_to_markdown_links(self):
        """DISPLAY mode converts citations to clickable markdown links."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        Research shows [1] that this works.

        [1]: https://example.com/study.pdf
        """

        agent.append(content)
        message = agent.messages[-1]

        rendered = message.render(RenderMode.DISPLAY)

        # Should have markdown link format [domain](url)
        assert (
            "[example.com](https://example.com/study.pdf)" in rendered
            or "[1]" in rendered
        )
        # Reference block should be removed
        assert "[1]:" not in rendered

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_render_display_tool_message_shows_urls(self):
        """DISPLAY mode for tool messages shows url attributes."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        <results>
            <item idx="1" />
            <item idx="2" />
        </results>
        """
        citations = ["https://example.com/item1", "https://example.com/item2"]

        agent.append(content, role="tool", citations=citations)
        message = agent.messages[-1]

        rendered = message.render(RenderMode.DISPLAY)

        # idx should convert to url for display
        assert 'url="https://example.com/item1"' in rendered or 'idx="1"' in rendered

        await agent.async_close()


class TestMessageRenderingForLLM:
    """Test message rendering for LLM consumption."""

    @pytest.mark.asyncio
    async def test_render_llm_uses_global_indices(self):
        """LLM mode uses global indices from CitationIndex."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # First message establishes global index
        agent.append(
            """
            First doc [1].

            [1]: https://example.com/doc1
            """
        )

        # Second message should use global indices
        agent.append(
            """
            Second doc [1].

            [1]: https://example.com/doc2
            """
        )

        # Get global indices
        global_idx_1 = manager.index.lookup("https://example.com/doc1")
        global_idx_2 = manager.index.lookup("https://example.com/doc2")

        assert global_idx_1 is not None
        assert global_idx_2 is not None
        assert global_idx_1 != global_idx_2

        # Render both messages for LLM
        msg1_llm = agent.messages[-2].render(RenderMode.LLM)
        msg2_llm = agent.messages[-1].render(RenderMode.LLM)

        # Should use global indices
        assert f"[!CITE_{global_idx_1}!]" in msg1_llm
        assert f"[!CITE_{global_idx_2}!]" in msg2_llm

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_render_llm_reuses_global_index_for_same_url(self):
        """Same URL gets same global index across messages."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        url = "https://example.com/doc"

        # First message
        agent.append(f"First reference [1].\n\n[1]: {url}")

        # Second message with same URL
        agent.append(f"Second reference [1].\n\n[1]: {url}")

        global_idx = manager.index.lookup(url)

        # Both messages should use the same global index when rendered
        msg1_llm = agent.messages[-2].render(RenderMode.LLM)
        msg2_llm = agent.messages[-1].render(RenderMode.LLM)

        assert f"[!CITE_{global_idx}!]" in msg1_llm
        assert f"[!CITE_{global_idx}!]" in msg2_llm

        await agent.async_close()


class TestMixedFormatHandling:
    """Test handling of mixed markdown/XML content."""

    @pytest.mark.asyncio
    async def test_mixed_markdown_and_xml_citations(self):
        """Messages with both markdown and XML citations work correctly."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        Text citation [1] and XML data:

        <items>
            <item url="https://example.com/xml-doc" />
        </items>

        [1]: https://example.com/text-doc
        """

        agent.append(content, role="tool")
        message = agent.messages[-1]

        # Both citations should be extracted
        assert message.citations is not None
        assert len(message.citations) >= 2

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_xml_href_attributes_also_extracted(self):
        """XML href attributes are treated like url attributes."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        <links>
            <link href="https://example.com/link1" />
            <link href="https://example.com/link2" />
        </links>
        """

        # Parse should extract href attributes
        parsed, citations = manager.parse(content, content_format="llm")

        assert len(citations) >= 2
        assert any("link1" in str(c) for c in citations)

        await agent.async_close()
