"""
Tests for global citation index coordination.

Focuses on:
- Same URL always gets same global index
- Local-to-global index mapping
- Citation lookup from global index
- Sparse index handling
"""

import pytest
from good_agent import Agent, AssistantMessage
from good_agent.extensions.citations import CitationIndex, CitationManager


class TestGlobalIndexConsistency:
    """Test that global index maintains consistent mappings."""

    @pytest.mark.asyncio
    async def test_same_url_same_global_index(self):
        """Same URL always gets the same global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        url = "https://example.com/doc.pdf"

        # Add URL multiple times across different messages
        agent.append(f"First: [1]\n\n[1]: {url}")
        agent.append(f"Second: [1]\n\n[1]: {url}")
        agent.append(f"Third: [1]\n\n[1]: {url}")

        # All should map to the same global index
        global_idx = manager.index.lookup(url)
        assert global_idx is not None

        # Check that index only appears once
        assert len(manager.index) == 1

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_different_urls_different_indices(self):
        """Different URLs get different global indices."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        url1 = "https://example.com/doc1.pdf"
        url2 = "https://example.com/doc2.pdf"

        agent.append(f"First: [1]\n\n[1]: {url1}")
        agent.append(f"Second: [1]\n\n[1]: {url2}")

        idx1 = manager.index.lookup(url1)
        idx2 = manager.index.lookup(url2)

        assert idx1 != idx2
        assert len(manager.index) == 2

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_global_index_sequential(self):
        """Global indices are assigned sequentially."""
        index = CitationIndex()

        idx1 = index.add("https://example.com/doc1")
        idx2 = index.add("https://example.com/doc2")
        idx3 = index.add("https://example.com/doc3")

        assert idx1 == 1
        assert idx2 == 2
        assert idx3 == 3


class TestLocalToGlobalMapping:
    """Test mapping between local message indices and global indices."""

    @pytest.mark.asyncio
    async def test_local_indices_mapped_to_global(self):
        """Local message indices map to correct global indices."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # First message: establishes doc1 as global index 1
        agent.append("Text [1]\n\n[1]: https://example.com/doc1")

        # Second message: doc2 gets global index 2, but is local index 1
        agent.append("Text [1]\n\n[1]: https://example.com/doc2")

        msg2 = agent.messages[-1]
        assert msg2.citations is not None
        # Message has local index 1
        assert len(msg2.citations) == 1

        # But maps to global index 2
        global_idx = manager.index.lookup(str(msg2.citations[0]))
        assert global_idx == 2

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_message_with_multiple_citations_maps_correctly(self):
        """Message with multiple citations maps each to global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # Pre-populate global index
        manager.index.add("https://example.com/doc1")
        manager.index.add("https://example.com/doc2")

        # Message references both in local order
        agent.append(
            "Text [1] and [2]\n\n[1]: https://example.com/doc2\n[2]: https://example.com/doc1"
        )

        message = agent.messages[-1]

        # Local citations are in message order
        assert message.citations is not None
        assert str(message.citations[0]) == "https://example.com/doc2"
        assert str(message.citations[1]) == "https://example.com/doc1"

        # But global indices are consistent
        assert manager.index.lookup("https://example.com/doc1") == 1
        assert manager.index.lookup("https://example.com/doc2") == 2

        await agent.async_close()


class TestCitationLookup:
    """Test looking up citations from global index."""

    @pytest.mark.asyncio
    async def test_lookup_citation_by_index(self):
        """Can look up citation URL by global index."""
        index = CitationIndex()
        url = "https://example.com/doc"

        idx = index.add(url)
        retrieved = index[idx]

        assert str(retrieved) == url

    @pytest.mark.asyncio
    async def test_lookup_index_by_url(self):
        """Can look up global index by URL."""
        index = CitationIndex()
        url = "https://example.com/doc"

        idx = index.add(url)
        looked_up = index.lookup(url)

        assert looked_up == idx

    @pytest.mark.asyncio
    async def test_lookup_nonexistent_url_returns_none(self):
        """Looking up non-existent URL returns None."""
        index = CitationIndex()

        result = index.lookup("https://nonexistent.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_llm_response_lookups_citations_from_global_index(self):
        """LLM response with [1], [2] should resolve from global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # Populate global index
        agent.append(
            """
            Sources:

            [1]: https://example.com/source1
            [2]: https://example.com/source2
            [3]: https://example.com/source3
            """
        )

        # Simulate LLM response that just has references (no URLs)
        llm_response = AssistantMessage(
            """
            Based on [1] and [2], we conclude X.
            Additional evidence from [3] supports this.
            """
        )

        agent.append(llm_response)
        message = agent.messages[-1]

        # Citations should be resolved from global index
        assert message.citations is not None
        assert len(message.citations) == 3
        assert str(message.citations[0]) == "https://example.com/source1"
        assert str(message.citations[1]) == "https://example.com/source2"
        assert str(message.citations[2]) == "https://example.com/source3"

        await agent.async_close()


class TestSparseIndexHandling:
    """Test handling of non-sequential citation indices."""

    @pytest.mark.asyncio
    async def test_sparse_indices_compacted_to_sequential(self):
        """Sparse indices [1], [5], [10] are compacted in message.citations."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        content = """
        References [1], [5], and [10].

        [1]: https://example.com/doc1
        [5]: https://example.com/doc5
        [10]: https://example.com/doc10
        """

        agent.append(content)
        message = agent.messages[-1]

        # Message citations are sequential
        assert len(message.citations) == 3
        assert str(message.citations[0]) == "https://example.com/doc1"
        assert str(message.citations[1]) == "https://example.com/doc5"
        assert str(message.citations[2]) == "https://example.com/doc10"

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_sparse_references_remapped_in_content(self):
        """Sparse references in content are remapped to sequential."""
        manager = CitationManager()

        content = """
        References [1], [5], and [10].

        [1]: https://example.com/doc1
        [5]: https://example.com/doc5
        [10]: https://example.com/doc10
        """

        parsed, citations = manager.parse(content, content_format="llm")

        # Should have sequential citations in content
        assert "[!CITE_1!]" in parsed
        assert "[!CITE_2!]" in parsed
        assert "[!CITE_3!]" in parsed

        # Original sparse indices should not appear
        assert "[!CITE_5!]" not in parsed
        assert "[!CITE_10!]" not in parsed


class TestIndexMerging:
    """Test merging local citations into global index."""

    @pytest.mark.asyncio
    async def test_merge_returns_local_to_global_mapping(self):
        """Index.merge() returns mapping from local to global indices."""
        index = CitationIndex()

        # Pre-populate with one URL
        index.add("https://example.com/existing")

        # Merge new citations
        local_citations = [
            "https://example.com/new1",
            "https://example.com/existing",  # Duplicate
            "https://example.com/new2",
        ]

        mapping = index.merge(local_citations)

        # Local index 1 -> global index 2 (new1)
        assert mapping[1] == 2
        # Local index 2 -> global index 1 (existing, already in index)
        assert mapping[2] == 1
        # Local index 3 -> global index 3 (new2)
        assert mapping[3] == 3

    @pytest.mark.asyncio
    async def test_merge_adds_new_citations_to_index(self):
        """Merging adds new citations to global index."""
        index = CitationIndex()
        initial_count = len(index)

        local_citations = [
            "https://example.com/doc1",
            "https://example.com/doc2",
        ]

        index.merge(local_citations)

        assert len(index) == initial_count + 2
