from __future__ import annotations

import re
from enum import Enum
from typing import NamedTuple

from good_agent.core.types import URL


class CitationFormat(Enum):
    """Citation format types."""

    MARKDOWN = "markdown"  # [1], [2], [3]
    LLM = "llm"  # [!CITE_1!], [!CITE_2!]
    XML_IDX = "xml_idx"  # idx="1", idx="2"
    XML_URL = "xml_url"  # url="https://..."
    UNKNOWN = "unknown"


class CitationMatch(NamedTuple):
    """A detected citation match in text."""

    format: CitationFormat
    start: int
    end: int
    original_text: str
    citation_index: int | None = None  # Renamed to avoid shadowing tuple.index()
    url: URL | None = None


class CitationPatterns:
    """Regular expression patterns for different citation formats."""

    # Text patterns - group 1 should capture the index
    MARKDOWN = re.compile(r"\[(\d+)\]")
    LLM_CITE = re.compile(r"\[!CITE_(\d+)!\]")

    # XML patterns - group 1 captures the value
    XML_IDX_ATTR = re.compile(r'idx="(\d+)"')
    XML_URL_ATTR = re.compile(r'(?:url|href)="([^"]+)"')  # Matches both url and href attributes

    # Block patterns for markdown reference lists
    # Supports both plain URLs and URLs wrapped in angle brackets <...>
    # Allow leading whitespace before reference blocks to support indented content
    MARKDOWN_REF_BLOCK = re.compile(r"^\s*\[(\d+)\]:\s*(?:<(.+?)>|(.+))$", re.MULTILINE)

    # Pattern for already-processed reference blocks that got converted to [!CITE_X!]: [!CITE_Y!] format
    PROCESSED_REF_BLOCK = re.compile(r"^\s*\[!CITE_\d+!\]:\s*\[!CITE_\d+!\]\s*$", re.MULTILINE)

    @classmethod
    def detect_format(cls, text: str) -> CitationFormat:
        """
        Detect the primary citation format in text.

        Args:
            text: Text content to analyze

        Returns:
            Most likely CitationFormat

        Example:
            >>> CitationPatterns.detect_format("See [1] and [2]")
            CitationFormat.MARKDOWN
            >>> CitationPatterns.detect_format("Check [!CITE_1!] for details")
            CitationFormat.LLM
        """
        # Count matches for each format
        counts = {
            CitationFormat.MARKDOWN: len(cls.MARKDOWN.findall(text)),
            CitationFormat.LLM: len(cls.LLM_CITE.findall(text)),
            CitationFormat.XML_IDX: len(cls.XML_IDX_ATTR.findall(text)),
            CitationFormat.XML_URL: len(cls.XML_URL_ATTR.findall(text)),
        }

        # Return format with highest count, or UNKNOWN if no matches
        max_format = max(counts, key=lambda k: counts[k])
        return max_format if counts[max_format] > 0 else CitationFormat.UNKNOWN


class CitationExtractor:
    """Extract citations from text content."""

    @staticmethod
    def extract_citations(text: str, format: CitationFormat | None = None) -> list[CitationMatch]:
        """
        Extract all citations from text.

        Args:
            text: Text content to extract from
            format: Specific format to look for (auto-detect if None)

        Returns:
            List of CitationMatch objects

        Example:
            >>> extractor = CitationExtractor()
            >>> matches = extractor.extract_citations("See [1] and [2]")
            >>> len(matches)
            2
            >>> matches[0].citation_index
            1
        """
        if format is None:
            format = CitationPatterns.detect_format(text)

        matches = []

        if format == CitationFormat.MARKDOWN:
            for match in CitationPatterns.MARKDOWN.finditer(text):
                matches.append(
                    CitationMatch(
                        format=CitationFormat.MARKDOWN,
                        start=match.start(),
                        end=match.end(),
                        original_text=match.group(0),
                        citation_index=int(match.group(1)),
                    )
                )

        elif format == CitationFormat.LLM:
            for match in CitationPatterns.LLM_CITE.finditer(text):
                matches.append(
                    CitationMatch(
                        format=CitationFormat.LLM,
                        start=match.start(),
                        end=match.end(),
                        original_text=match.group(0),
                        citation_index=int(match.group(1)),
                    )
                )

        elif format == CitationFormat.XML_IDX:
            for match in CitationPatterns.XML_IDX_ATTR.finditer(text):
                matches.append(
                    CitationMatch(
                        format=CitationFormat.XML_IDX,
                        start=match.start(),
                        end=match.end(),
                        original_text=match.group(0),
                        citation_index=int(match.group(1)),
                    )
                )

        elif format == CitationFormat.XML_URL:
            for match in CitationPatterns.XML_URL_ATTR.finditer(text):
                matches.append(
                    CitationMatch(
                        format=CitationFormat.XML_URL,
                        start=match.start(),
                        end=match.end(),
                        original_text=match.group(0),
                        url=URL(match.group(1)),
                    )
                )

        return matches

    @staticmethod
    def extract_markdown_references(text: str) -> dict[int, URL]:
        """
        Extract markdown reference block citations.

        Parses blocks like:
        [1]: https://example.com
        [2]: https://other.com
        [3]: <https://example.com/with/angle/brackets>

        Args:
            text: Text containing reference blocks

        Returns:
            Dictionary mapping index to URL

        Example:
            >>> text = '''
            ... [1]: https://example.com
            ... [2]: https://other.com
            ... [3]: <https://example.com/with/brackets>
            ... '''
            >>> refs = CitationExtractor.extract_markdown_references(text)
            >>> refs[1]
            URL("https://example.com")
            >>> refs[3]
            URL("https://example.com/with/brackets")
        """
        references = {}

        for match in CitationPatterns.MARKDOWN_REF_BLOCK.finditer(text):
            index = int(match.group(1))
            # Group 2 captures URLs in angle brackets, group 3 captures bare URLs
            # Use whichever one matched
            url_str = match.group(2) or match.group(3)
            url = URL(url_str.strip())
            references[index] = url

        return references


class CitationTransformer:
    """Transform citations between different formats."""

    @staticmethod
    def transform_to_llm_format(
        text: str,
        index_mapping: dict[int, int] | None = None,
        source_format: CitationFormat | None = None,
    ) -> str:
        """
        Transform citations to LLM-optimized format [!CITE_X!].

        Args:
            text: Text with citations to transform
            index_mapping: Optional mapping from local to global indices
            source_format: Source format (auto-detected if None)

        Returns:
            Text with citations in LLM format

        Example:
            >>> transformer = CitationTransformer()
            >>> text = "See [1] and [2]"
            >>> mapping = {1: 101, 2: 102}  # Local -> Global
            >>> result = transformer.transform_to_llm_format(text, mapping)
            >>> result
            "See [!CITE_101!] and [!CITE_102!]"
        """
        if source_format is None:
            source_format = CitationPatterns.detect_format(text)

        if index_mapping is None:
            index_mapping = {}

        result = text

        # Handle mixed formats by transforming all patterns found
        # This is necessary because content may have both [!CITE_X!] and idx="X" patterns

        if source_format == CitationFormat.MARKDOWN:

            def replace_markdown(match):
                local_idx = int(match.group(1))
                global_idx = index_mapping.get(local_idx, local_idx)
                return f"[!CITE_{global_idx}!]"

            result = CitationPatterns.MARKDOWN.sub(replace_markdown, result)

        # For LLM and XML_IDX formats, transform both patterns to handle mixed content
        if source_format in (CitationFormat.XML_IDX, CitationFormat.LLM):
            # Transform XML idx attributes
            def replace_xml_idx(match):
                local_idx = int(match.group(1))
                global_idx = index_mapping.get(local_idx, local_idx)
                return f'idx="{global_idx}"'

            result = CitationPatterns.XML_IDX_ATTR.sub(replace_xml_idx, result)

            # Transform LLM cite patterns
            if index_mapping:

                def replace_llm_cite(match):
                    local_idx = int(match.group(1))
                    global_idx = index_mapping.get(local_idx, local_idx)
                    return f"[!CITE_{global_idx}!]"

                result = CitationPatterns.LLM_CITE.sub(replace_llm_cite, result)

        return result

    @staticmethod
    def transform_to_user_format(
        text: str,
        citations: list[URL] | None = None,
        source_format: CitationFormat | None = None,
    ) -> str:
        """
        Transform citations to user-friendly format with clickable links.

        Args:
            text: Text with citations to transform
            citations: List of URLs corresponding to citation indices
            source_format: Source format (auto-detected if None)

        Returns:
            Text with citations as markdown links

        Example:
            >>> transformer = CitationTransformer()
            >>> text = "See [!CITE_1!]"
            >>> urls = ["https://example.com"]
            >>> result = transformer.transform_to_user_format(text, urls)
            >>> result
            "See [example.com](https://example.com)"
        """
        if citations is None:
            citations = []

        result = text

        # Handle mixed formats by applying all transformations that match
        # Check for LLM format citations [!CITE_X!]
        if CitationPatterns.LLM_CITE.search(result):

            def replace_llm_cite(match):
                index = int(match.group(1))
                # Convert to 0-based for list access
                if 1 <= index <= len(citations):
                    url = citations[index - 1]
                    # Extract domain for link text
                    domain = _extract_domain(str(url))
                    return f"[{domain}]({url})"
                else:
                    return match.group(0)  # Leave unchanged if invalid

            result = CitationPatterns.LLM_CITE.sub(replace_llm_cite, result)

        # Check for markdown format citations [N]
        if CitationPatterns.MARKDOWN.search(result):

            def replace_markdown(match):
                index = int(match.group(1))
                # Convert to 0-based for list access
                if 1 <= index <= len(citations):
                    url = citations[index - 1]
                    domain = _extract_domain(str(url))
                    return f"[{domain}]({url})"
                else:
                    return match.group(0)  # Leave unchanged if invalid

            result = CitationPatterns.MARKDOWN.sub(replace_markdown, result)

        # Check for XML idx attributes idx="N"
        if CitationPatterns.XML_IDX_ATTR.search(result):
            # Convert idx="N" to url="..." for user display
            def replace_xml_idx(match):
                index = int(match.group(1))
                # Convert to 0-based for list access
                if 1 <= index <= len(citations):
                    url = citations[index - 1]
                    return f'url="{url}"'
                else:
                    return match.group(0)  # Leave unchanged if invalid

            result = CitationPatterns.XML_IDX_ATTR.sub(replace_xml_idx, result)

        # XML_URL format stays as-is since URLs are already visible

        return result

    @staticmethod
    def extract_and_normalize_citations(
        text: str, citations: list[URL] | None = None
    ) -> tuple[str, list[URL]]:
        """
        Extract citations from mixed-format text and normalize to local format.

        This handles text that may contain:
        - Inline URLs that should become citations
        - Mixed citation formats
        - Reference blocks

        Args:
            text: Text content with various citation formats
            citations: Existing citations list to extend

        Returns:
            Tuple of (normalized_text, citations_list)

        Example:
            >>> text = "See https://example.com and [1]"
            >>> normalized, cites = CitationTransformer.extract_and_normalize_citations(
            ...     text
            ... )
            >>> normalized
            "See [!CITE_1!] and [!CITE_1!]"
            >>> cites
            [URL("https://example.com")]
        """
        if citations is None:
            citations = []

        # Start with copy of existing citations
        result_citations = list(citations)
        result_text = text

        # 1. Find and extract inline URLs (convert to citations)
        url_pattern = re.compile(r"https?://[^\s\]]+")
        url_matches = list(url_pattern.finditer(result_text))

        # Process URLs in reverse order to maintain positions
        for match in reversed(url_matches):
            url = URL(match.group(0))

            # Check if URL already in citations
            try:
                index = result_citations.index(url)
            except ValueError:
                # Add new citation
                result_citations.append(url)
                index = len(result_citations) - 1

            # Replace URL with local citation (1-based)
            citation_ref = f"[!CITE_{index + 1}!]"
            result_text = result_text[: match.start()] + citation_ref + result_text[match.end() :]

        # 2. Handle any existing citation references (normalize to local indices)
        format = CitationPatterns.detect_format(result_text)

        if format == CitationFormat.MARKDOWN:
            # If we find [1], [2] assume they reference result_citations by index
            # This normalizes them to [!CITE_1!], [!CITE_2!] format
            def replace_markdown(match):
                index = int(match.group(1))
                return f"[!CITE_{index}!]"

            result_text = CitationPatterns.MARKDOWN.sub(replace_markdown, result_text)

        return result_text, result_citations


def _extract_domain(url: str) -> str:
    """Extract domain from URL for display purposes."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. prefix if present
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url
