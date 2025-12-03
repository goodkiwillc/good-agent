import pytest
from good_agent.extensions.citations import CitationManager


class TestContentCitationParsing:
    @pytest.mark.asyncio
    async def test_basic_markdown_parsing(self):
        citation_manager = CitationManager()

        content = """\
        This is a sample markdown content with citations [1] and [2].
        Here is another reference to [1].

        [1]: https://example.com/source1.pdf
        [2]: https://example.com/source2.html
        """

        parsed_content, extracted_citations = citation_manager.parse(
            content, content_format="markdown"
        )

        assert (
            parsed_content.strip()
            == """\
This is a sample markdown content with citations [1] and [2].
        Here is another reference to [1]."""
        )

    @pytest.mark.asyncio
    async def test_basic_parsing_llm_format(self):
        citation_manager = CitationManager()

        content = """\
        This is a sample content with citations [1] and [2].
        Here is another reference to [1].

        [1]: https://example.com/source1.pdf
        [2]: https://example.com/source2.html
        """

        citations = [
            "https://example.com/source1.pdf",
            "https://example.com/source2.html",
        ]

        parsed_content, extracted_citations = citation_manager.parse(content, content_format="llm")

        assert (
            parsed_content.strip()
            == """\
This is a sample content with citations [!CITE_1!] and [!CITE_2!].
        Here is another reference to [!CITE_1!]."""
        )

        assert extracted_citations == citations

    @pytest.mark.asyncio
    async def test_no_citations(self):
        citation_manager = CitationManager()

        content = "This is content without any citations."
        parsed_content, extracted_citations = citation_manager.parse(
            content, content_format="markdown"
        )

        assert parsed_content == content
        assert extracted_citations == []

    @pytest.mark.asyncio
    async def test_parse_markdown_with_xml(self):
        citation_manager = CitationManager()

        content = """\
        This content uses XML-style tags for some sections.

        Here's a normal citation reference [1].

        <entities>
            <entity>
               Name: Example
               <profiles>
                  <link href="https://example.com/profile1" />
                  <link href="https://example.com/profile2" />
               </profiles>
            </entity>
        </entities>

        [1]: https://example.com/source1.pdf

        """

        parsed_content, extracted_citations = citation_manager.parse(
            content, content_format="markdown"
        )

        assert (
            parsed_content.strip()
            == """\
This content uses XML-style tags for some sections.

        Here's a normal citation reference [1].

        <entities>
            <entity>
               Name: Example
               <profiles>
                  <link href="https://example.com/profile1" />
                  <link href="https://example.com/profile2" />
               </profiles>
            </entity>
        </entities>"""
        )
        assert extracted_citations == [
            "https://example.com/source1.pdf",
        ]

    @pytest.mark.asyncio
    async def test_parse_markdown_with_xml_llm(self):
        citation_manager = CitationManager()

        content = """\
        This content uses XML-style tags for some sections.

        Here's a normal citation reference [1].

        <entities>
            <entity>
               Name: Example
               <profiles>
                  <link href="https://example.com/profile1" />
                  <link href="https://example.com/profile2" />
               </profiles>
            </entity>
        </entities>
        [1]: https://example.com/source1.pdf
        """

        parsed_content, extracted_citations = citation_manager.parse(content, content_format="llm")

        assert (
            parsed_content.strip()
            == """\
This content uses XML-style tags for some sections.

        Here's a normal citation reference [!CITE_1!].

        <entities>
            <entity>
               Name: Example
               <profiles>
                  <link idx="2" />
                  <link idx="3" />
               </profiles>
            </entity>
        </entities>"""
        )

        assert extracted_citations == [
            "https://example.com/source1.pdf",
            "https://example.com/profile1",
            "https://example.com/profile2",
        ]

    @pytest.mark.asyncio
    async def test_malformed_citations(self):
        citation_manager = CitationManager()

        content = """\
        This content has a malformed citation [1].

        [1] https://example.com/source1.pdf  # Missing colon
        """

        parsed_content, extracted_citations = citation_manager.parse(
            content, content_format="markdown"
        )

        assert (
            parsed_content.strip()
            == """\
This content has a malformed citation [1]."""
        )
        assert extracted_citations == [
            "https://example.com/source1.pdf"
        ]  # Should still extract the URL

    @pytest.mark.asyncio
    async def test_alternative_markdown_formats(self):
        citation_manager = CitationManager()

        content = """\
        This content uses an alternative citation format [cite1].

        [cite1]: https://example.com/source1.pdf
        """

        parsed_content, extracted_citations = citation_manager.parse(content)

        assert (
            parsed_content.strip()
            == """\
This content uses an alternative citation format [cite1]."""
        )
        assert extracted_citations == ["https://example.com/source1.pdf"]

        content = """\
        This content uses inline citations (see https://example.com/source1.pdf).
        """

        parsed_content, extracted_citations = citation_manager.parse(content)
        assert (
            parsed_content.strip()
            == """\
This content uses inline citations (see https://example.com/source1.pdf)."""
        )
        assert extracted_citations == ["https://example.com/source1.pdf"]

    @pytest.mark.asyncio
    async def test_multiple_url_formats(self):
        """Test handling of various URL patterns in content."""
        citation_manager = CitationManager()

        content = """\
        Multiple URLs in different contexts:
        - Direct: https://example.com/page1
        - Parentheses: (see https://example.com/page2)
        - Angle brackets: <https://example.com/page4>
        """

        _, extracted_citations = citation_manager.parse(content, content_format="markdown")

        # Should extract URLs (excluding those in quotes to avoid href conflicts)
        assert len(extracted_citations) == 3
        assert "https://example.com/page1" in extracted_citations
        assert "https://example.com/page2" in extracted_citations
        assert "https://example.com/page4" in extracted_citations

    @pytest.mark.asyncio
    async def test_mixed_reference_styles(self):
        """Test handling of mixed citation styles."""
        citation_manager = CitationManager()

        content = """\
        Text with numeric [1] and named [source] references.

        [1]: https://example.com/source1.pdf
        [source]: https://example.com/source2.html
        """

        _, extracted_citations = citation_manager.parse(content, content_format="markdown")

        # Should extract both citations
        assert len(extracted_citations) == 2
        assert "https://example.com/source1.pdf" in extracted_citations
        assert "https://example.com/source2.html" in extracted_citations

    @pytest.mark.asyncio
    async def test_sparse_reference_indices(self):
        """Test handling of non-sequential reference indices."""
        citation_manager = CitationManager()

        content = """\
        References [1], [3], and [5].

        [1]: https://example.com/first
        [3]: https://example.com/third
        [5]: https://example.com/fifth
        """

        _, extracted_citations = citation_manager.parse(content, content_format="llm")

        # Should preserve the references but extract in order
        assert len(extracted_citations) == 3
        # Citations should be in index order
        assert extracted_citations == [
            "https://example.com/first",
            "https://example.com/third",
            "https://example.com/fifth",
        ]

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """Test parsing empty or whitespace-only content."""
        citation_manager = CitationManager()

        # Empty string
        parsed, citations = citation_manager.parse("", content_format="markdown")
        assert parsed == ""
        assert citations == []

        # Whitespace only
        parsed, citations = citation_manager.parse("   \n\n   ", content_format="markdown")
        assert parsed.strip() == ""
        assert citations == []
