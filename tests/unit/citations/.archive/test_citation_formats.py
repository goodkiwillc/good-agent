"""
Unit tests for citation format detection and transformation.

Tests the citation format utilities including:
- Format detection (markdown, LLM, XML, etc.)
- Citation extraction from text
- Format transformation between different types
- Edge cases and malformed citations
"""

from good_agent.extensions.citations import (
    CitationExtractor,
    CitationFormat,
    CitationPatterns,
    CitationTransformer,
)
from goodintel_core.types import URL


class TestCitationPatterns:
    """Test citation pattern matching and detection."""

    def test_detect_markdown_format(self):
        """Test detecting markdown citation format."""
        text = "According to the study [1] and research [2], we found..."
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.MARKDOWN

        # Multiple citations
        text = "See [1], [2], and [3] for details"
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.MARKDOWN

    def test_detect_llm_format(self):
        """Test detecting LLM citation format."""
        text = "The report [!CITE_1!] shows that [!CITE_2!] indicates..."
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.LLM

        # High-numbered citations
        text = "Source [!CITE_123!] and [!CITE_456!]"
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.LLM

    def test_detect_xml_idx_format(self):
        """Test detecting XML idx attribute format."""
        text = '<item idx="1">Content</item><ref idx="2"/>'
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.XML_IDX

    def test_detect_xml_url_format(self):
        """Test detecting XML url attribute format."""
        text = '<item url="https://example.com">Content</item>'
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.XML_URL

    def test_detect_unknown_format(self):
        """Test detecting unknown format."""
        text = "No citations here, just plain text."
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.UNKNOWN

    def test_detect_mixed_formats(self):
        """Test detecting dominant format in mixed text."""
        # More markdown than LLM
        text = "See [1], [2], [3] and also [!CITE_1!]"
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.MARKDOWN

        # More LLM than markdown
        text = "Check [!CITE_1!], [!CITE_2!], [!CITE_3!] and [1]"
        format = CitationPatterns.detect_format(text)
        assert format == CitationFormat.LLM


class TestCitationExtractor:
    """Test citation extraction from text."""

    def test_extract_markdown_citations(self):
        """Test extracting markdown citations."""
        text = "The study [1] shows that [2] indicates important findings [3]."

        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)

        assert len(matches) == 3
        assert matches[0].citation_index == 1
        assert matches[1].citation_index == 2
        assert matches[2].citation_index == 3

        # Check positions
        assert matches[0].original_text == "[1]"
        assert matches[1].original_text == "[2]"
        assert matches[2].original_text == "[3]"

    def test_extract_llm_citations(self):
        """Test extracting LLM format citations."""
        text = "According to [!CITE_5!] and [!CITE_10!], the results..."

        matches = CitationExtractor.extract_citations(text, CitationFormat.LLM)

        assert len(matches) == 2
        assert matches[0].citation_index == 5
        assert matches[1].citation_index == 10
        assert matches[0].original_text == "[!CITE_5!]"
        assert matches[1].original_text == "[!CITE_10!]"

    def test_extract_xml_idx_citations(self):
        """Test extracting XML idx citations."""
        text = (
            '<search_result idx="1">Result 1</search_result><item idx="2">Item</item>'
        )

        matches = CitationExtractor.extract_citations(text, CitationFormat.XML_IDX)

        assert len(matches) == 2
        assert matches[0].citation_index == 1
        assert matches[1].citation_index == 2
        assert matches[0].original_text == 'idx="1"'
        assert matches[1].original_text == 'idx="2"'

    def test_extract_xml_url_citations(self):
        """Test extracting XML url citations."""
        text = '<item url="https://example.com">Example</item><ref url="https://test.org"/>'

        matches = CitationExtractor.extract_citations(text, CitationFormat.XML_URL)

        assert len(matches) == 2
        assert matches[0].url == URL("https://example.com")
        assert matches[1].url == URL("https://test.org")
        assert matches[0].original_text == 'url="https://example.com"'
        assert matches[1].original_text == 'url="https://test.org"'

    def test_extract_with_auto_detection(self):
        """Test extraction with automatic format detection."""
        text = "Study [1] and research [2] show..."

        matches = CitationExtractor.extract_citations(text)  # No format specified

        assert len(matches) == 2
        assert matches[0].format == CitationFormat.MARKDOWN
        assert matches[0].citation_index == 1
        assert matches[1].citation_index == 2

    def test_extract_markdown_references(self):
        """Test extracting markdown reference blocks."""
        text = """
Some content here.

[1]: https://example.com/study
[2]: https://research.org/paper
[3]: https://news.com/article

More content here.
        """

        references = CitationExtractor.extract_markdown_references(text)

        assert len(references) == 3
        assert references[1] == URL("https://example.com/study")
        assert references[2] == URL("https://research.org/paper")
        assert references[3] == URL("https://news.com/article")

    def test_extract_no_citations(self):
        """Test extracting from text with no citations."""
        text = "This text has no citations at all."

        matches = CitationExtractor.extract_citations(text)
        assert len(matches) == 0

        references = CitationExtractor.extract_markdown_references(text)
        assert len(references) == 0


class TestCitationTransformer:
    """Test citation format transformations."""

    def test_transform_markdown_to_llm(self):
        """Test transforming markdown citations to LLM format."""
        text = "The study [1] shows that [2] indicates results."

        result = CitationTransformer.transform_to_llm_format(
            text, source_format=CitationFormat.MARKDOWN
        )

        expected = "The study [!CITE_1!] shows that [!CITE_2!] indicates results."
        assert result == expected

    def test_transform_markdown_to_llm_with_mapping(self):
        """Test transforming with index mapping."""
        text = "See [1] and [2] for details."
        mapping = {1: 101, 2: 102}  # Local -> Global mapping

        result = CitationTransformer.transform_to_llm_format(
            text, mapping, CitationFormat.MARKDOWN
        )

        expected = "See [!CITE_101!] and [!CITE_102!] for details."
        assert result == expected

    def test_transform_xml_idx_to_llm(self):
        """Test transforming XML idx to LLM format."""
        text = '<item idx="1">Content</item><ref idx="2"/>'
        mapping = {1: 5, 2: 6}

        result = CitationTransformer.transform_to_llm_format(
            text, mapping, CitationFormat.XML_IDX
        )

        expected = '<item idx="5">Content</item><ref idx="6"/>'
        assert result == expected

    def test_transform_llm_with_remapping(self):
        """Test transforming LLM format with new indices."""
        text = "Check [!CITE_1!] and [!CITE_2!]"
        mapping = {1: 10, 2: 11}

        result = CitationTransformer.transform_to_llm_format(
            text, mapping, CitationFormat.LLM
        )

        expected = "Check [!CITE_10!] and [!CITE_11!]"
        assert result == expected

    def test_transform_to_user_format(self):
        """Test transforming to user-friendly format."""
        text = "See [!CITE_1!] and [!CITE_2!] for details."
        citations = [
            URL("https://example.com/study"),
            URL("https://research.org/paper"),
        ]

        result = CitationTransformer.transform_to_user_format(
            text, citations, CitationFormat.LLM
        )

        expected = "See [example.com](https://example.com/study) and [research.org](https://research.org/paper) for details."
        assert result == expected

    def test_transform_markdown_to_user_format(self):
        """Test transforming markdown to user format."""
        text = "Study [1] and research [2]."
        citations = [URL("https://example.com"), URL("https://test.org")]

        result = CitationTransformer.transform_to_user_format(
            text, citations, CitationFormat.MARKDOWN
        )

        # URLs may have trailing slashes due to canonicalization
        assert "[example.com](https://example.com" in result
        assert "[test.org](https://test.org" in result
        assert "Study" in result and "research" in result

    def test_transform_with_invalid_indices(self):
        """Test transformation with invalid citation indices."""
        text = "See [!CITE_1!] and [!CITE_5!]"  # Index 5 doesn't exist
        citations = [URL("https://example.com")]  # Only 1 citation

        result = CitationTransformer.transform_to_user_format(
            text, citations, CitationFormat.LLM
        )

        # Should transform valid index, leave invalid unchanged
        assert "[example.com](https://example.com" in result  # May have trailing slash
        assert "[!CITE_5!]" in result  # Invalid index unchanged
        assert "See" in result and "and" in result

    def test_extract_and_normalize_citations(self):
        """Test extracting and normalizing mixed citation formats."""
        text = "Visit https://example.com and see [1] for more details."

        normalized_text, citations = (
            CitationTransformer.extract_and_normalize_citations(text)
        )

        # Should extract inline URL
        assert len(citations) == 1
        assert citations[0] == URL("https://example.com")

        # Should normalize text
        expected_text = "Visit [!CITE_1!] and see [!CITE_1!] for more details."
        assert normalized_text == expected_text

    def test_extract_and_normalize_with_existing_citations(self):
        """Test normalizing with existing citation list."""
        text = "New source https://new.com and existing [1]"
        existing_citations = [URL("https://existing.com")]

        normalized_text, citations = (
            CitationTransformer.extract_and_normalize_citations(
                text, existing_citations
            )
        )

        # Should extend existing citations
        assert len(citations) == 2
        assert citations[0] == URL("https://existing.com")  # Existing
        assert citations[1] == URL("https://new.com")  # New

        # Text should reference both
        expected_text = "New source [!CITE_2!] and existing [!CITE_1!]"
        assert normalized_text == expected_text

    def test_extract_and_normalize_duplicates(self):
        """Test handling duplicate URLs in normalization."""
        text = "Visit https://example.com and also https://example.com again."

        normalized_text, citations = (
            CitationTransformer.extract_and_normalize_citations(text)
        )

        # Should deduplicate URLs
        assert len(citations) == 1
        assert citations[0] == URL("https://example.com")

        # Both references should point to same citation
        expected_text = "Visit [!CITE_1!] and also [!CITE_1!] again."
        assert normalized_text == expected_text


class TestCitationFormatsEdgeCases:
    """Test edge cases and error conditions."""

    def test_malformed_citations(self):
        """Test handling malformed citation patterns."""
        # Markdown with letters
        text = "See [a] and [1b] for info"
        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)
        assert len(matches) == 0  # Should not match non-numeric

        # LLM format with malformed syntax
        text = "Check [!CITE_] and [!CITE_abc!]"
        matches = CitationExtractor.extract_citations(text, CitationFormat.LLM)
        assert len(matches) == 0  # Should not match malformed

        # XML with empty attributes
        text = '<item idx="">Content</item>'
        matches = CitationExtractor.extract_citations(text, CitationFormat.XML_IDX)
        assert len(matches) == 0  # Should not match empty

    def test_nested_citation_patterns(self):
        """Test handling nested or overlapping patterns."""
        # Nested brackets
        text = "See [[1]] and [2]"
        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)
        assert len(matches) == 2  # Should find both [1] and [2]

        # Mixed formats in same text
        text = "Check [1] and [!CITE_2!]"
        markdown_matches = CitationExtractor.extract_citations(
            text, CitationFormat.MARKDOWN
        )
        llm_matches = CitationExtractor.extract_citations(text, CitationFormat.LLM)

        assert len(markdown_matches) == 1
        assert len(llm_matches) == 1

    def test_unicode_in_citations(self):
        """Test handling Unicode in citation text."""
        # Unicode URLs
        text = 'Research at <item url="https://测试.com/文章">测试</item>'
        matches = CitationExtractor.extract_citations(text, CitationFormat.XML_URL)

        assert len(matches) == 1
        assert "测试.com" in str(matches[0].url)

        # Unicode around citations
        text = "研究 [1] 显示 [2] 结果"
        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)

        assert len(matches) == 2
        assert matches[0].citation_index == 1
        assert matches[1].citation_index == 2

    def test_very_large_indices(self):
        """Test handling very large citation indices."""
        text = "See [999999] and [!CITE_1000000!]"

        markdown_matches = CitationExtractor.extract_citations(
            text, CitationFormat.MARKDOWN
        )
        llm_matches = CitationExtractor.extract_citations(text, CitationFormat.LLM)

        assert len(markdown_matches) == 1
        assert markdown_matches[0].citation_index == 999999

        assert len(llm_matches) == 1
        assert llm_matches[0].citation_index == 1000000

    def test_transformation_with_empty_input(self):
        """Test transformations with empty or None inputs."""
        # Empty text
        result = CitationTransformer.transform_to_llm_format("")
        assert result == ""

        # None citations list
        result = CitationTransformer.transform_to_user_format(
            "Text [!CITE_1!]", None, CitationFormat.LLM
        )
        assert "[!CITE_1!]" in result  # Should be unchanged

        # Empty mapping
        result = CitationTransformer.transform_to_llm_format(
            "Text [1]", {}, CitationFormat.MARKDOWN
        )
        assert result == "Text [!CITE_1!]"  # Should use original indices

    def test_whitespace_handling(self):
        """Test handling of whitespace in citations."""
        # Extra whitespace in citations
        text = "Check [ 1 ] and [  2  ]"  # Spaces inside brackets
        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)
        assert len(matches) == 0  # Should not match with spaces

        # Proper citations with surrounding whitespace
        text = "Check [1]  and  [2]"
        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)
        assert len(matches) == 2  # Should match properly

    def test_citation_at_text_boundaries(self):
        """Test citations at beginning/end of text."""
        # Citation at start
        text = "[1] shows important results"
        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)
        assert len(matches) == 1
        assert matches[0].start == 0

        # Citation at end
        text = "Results are shown in [2]"
        matches = CitationExtractor.extract_citations(text, CitationFormat.MARKDOWN)
        assert len(matches) == 1
        assert matches[0].end == len(text)

        # Only citations
        text = "[!CITE_1!][!CITE_2!]"
        matches = CitationExtractor.extract_citations(text, CitationFormat.LLM)
        assert len(matches) == 2

    def test_complex_xml_structures(self):
        """Test citations in complex XML structures."""
        text = """
        <search_results>
            <result idx="1" title="First Result">
                <content url="https://example.com">Example content</content>
            </result>
            <result idx="2">
                <nested url="https://test.org" idx="3">Nested</nested>
            </result>
        </search_results>
        """

        idx_matches = CitationExtractor.extract_citations(text, CitationFormat.XML_IDX)
        url_matches = CitationExtractor.extract_citations(text, CitationFormat.XML_URL)

        assert len(idx_matches) == 3  # idx="1", idx="2", idx="3"
        assert len(url_matches) == 2  # Two URL attributes

        # Check specific matches
        indices = [m.citation_index for m in idx_matches]
        assert 1 in indices
        assert 2 in indices
        assert 3 in indices
