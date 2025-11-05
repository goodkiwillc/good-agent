import pytest
from good_agent.extensions.citations import CitationIndex
from goodintel_core.types import URL


class TestCitationIndexCore:
    """Core functionality tests for CitationIndex."""

    def test_initialization(self):
        """Test index initializes with correct offset."""
        # Default offset of 1
        index = CitationIndex()
        assert index.index_offset == 1
        assert len(index) == 0

        # Custom offset values
        index_custom = CitationIndex(index_offset=5)
        assert index_custom.index_offset == 5

        # First index should respect offset
        idx = index_custom.add("https://example.com")
        assert idx == 5

    def test_add_single_url(self):
        """Test adding a single URL returns correct index."""
        index = CitationIndex()

        # Add URL, should get index 1 (1-based)
        url = URL("https://example.com")
        idx = index.add(url)

        assert idx == 1
        assert len(index) == 1

        # Verify URL retrieval
        retrieved_url = index.get_url(1)
        assert retrieved_url == url

        # Verify lookup
        found_idx = index.lookup(url)
        assert found_idx == 1

    def test_add_duplicate_url(self):
        """Test adding duplicate URL returns same index."""
        index = CitationIndex()

        url = URL("https://example.com")

        # Add URL twice
        idx1 = index.add(url)
        idx2 = index.add(url)

        # Should return same index
        assert idx1 == idx2 == 1

        # Should still only have one entry
        assert len(index) == 1

    def test_url_canonicalization(self):
        """Test URL canonicalization for deduplication."""
        index = CitationIndex()

        # http vs https should be same
        url1 = URL("http://example.com/page")
        url2 = URL("https://example.com/page")

        idx1 = index.add(url1)
        idx2 = index.add(url2)

        assert idx1 == idx2  # Should be deduplicated
        assert len(index) == 1

        # Trailing slashes are NOT normalized by URL.canonicalize()
        # This is correct behavior - /page and /page/ are different resources
        url3 = URL("https://example.com/page/")
        idx3 = index.add(url3)

        assert idx3 != idx1  # Different URLs due to trailing slash
        assert len(index) == 2  # Two distinct URLs

        # Query parameter ordering
        url4 = URL("https://example.com/page?b=2&a=1")
        url5 = URL("https://example.com/page?a=1&b=2")

        idx4 = index.add(url4)
        idx5 = index.add(url5)

        assert idx4 == idx5  # Should be same due to sorted params

        # Fragment handling (fragments removed)
        url6 = URL("https://example.com/page?a=1&b=2#section")
        idx6 = index.add(url6)

        assert idx6 == idx4  # Same as previous (fragment removed)

    def test_lookup_operations(self):
        """Test bidirectional lookups."""
        index = CitationIndex()

        # Add some URLs
        url1 = URL("https://example.com")
        url2 = URL("https://test.org")

        idx1 = index.add(url1)
        idx2 = index.add(url2)

        # URL to index lookup
        assert index.lookup(url1) == idx1
        assert index.lookup(url2) == idx2

        # Index to URL lookup
        assert index.get_url(idx1) == URL("https://example.com")  # Canonicalized
        assert index.get_url(idx2) == URL("https://test.org")

        # Non-existent lookups return None
        assert index.lookup(URL("https://nonexistent.com")) is None
        assert index.get_url(999) is None

    def test_alias_handling(self):
        """Test URL alias/redirect management."""
        index = CitationIndex()

        # Add primary URL
        primary_url = URL("https://example.com/article")
        primary_idx = index.add(primary_url)

        # Add alias
        alias_url = URL("http://example.com/article")  # Different protocol
        alias_idx = index.add_alias(primary_url, alias_url)

        # Both should resolve to same index
        assert alias_idx == primary_idx
        assert index.lookup(alias_url) == primary_idx

        # Chain resolution - add alias to alias
        second_alias = URL("https://www.example.com/article")
        index.add_alias(alias_url, second_alias)

        assert index.lookup(second_alias) == primary_idx

        # Test error on non-existent primary
        with pytest.raises(ValueError):
            index.add_alias(URL("https://nonexistent.com"), URL("https://alias.com"))


class TestCitationIndexMerging:
    """Test merging local citations into global index."""

    def test_merge_new_citations(self):
        """Test merging citations not in index."""
        index = CitationIndex()

        # List of new URLs
        local_citations = [
            URL("https://example.com"),
            URL("https://test.org"),
            URL("https://research.edu"),
        ]

        # Merge into index
        mapping = index.merge(local_citations)

        # Should return local->global mapping (1-based)
        expected_mapping = {1: 1, 2: 2, 3: 3}
        assert mapping == expected_mapping

        # URLs should be added to index
        assert len(index) == 3
        assert index.get_url(1) == URL("https://example.com")
        assert index.get_url(2) == URL("https://test.org")
        assert index.get_url(3) == URL("https://research.edu")

    def test_merge_existing_citations(self):
        """Test merging citations already in index."""
        index = CitationIndex()

        # Pre-populate index
        existing_url = URL("https://example.com")
        existing_idx = index.add(existing_url)

        # Add another URL
        new_url = URL("https://test.org")
        new_idx = index.add(new_url)

        # Now merge list with mix of new and existing
        local_citations = [
            URL("https://example.com"),  # Existing
            URL("https://research.edu"),  # New
            URL("https://test.org"),  # Existing
        ]

        mapping = index.merge(local_citations)

        # Correct mapping should be returned
        expected_mapping = {1: existing_idx, 2: 3, 3: new_idx}  # New URL gets index 3
        assert mapping == expected_mapping

        # Index should have correct total
        assert len(index) == 3

    def test_merge_empty_list(self):
        """Test merging empty citation list."""
        index = CitationIndex()

        # Pre-populate with one item
        index.add(URL("https://example.com"))
        original_count = len(index)

        # Merge empty list
        mapping = index.merge([])

        # Returns empty mapping
        assert mapping == {}

        # Index unchanged
        assert len(index) == original_count

    def test_merge_preserves_order(self):
        """Test local index order preserved in mapping."""
        index = CitationIndex()

        # Add in specific order
        local_citations = [
            URL("https://c.com"),  # Should get local index 1 -> global index 1
            URL("https://a.com"),  # Should get local index 2 -> global index 2
            URL("https://b.com"),  # Should get local index 3 -> global index 3
        ]

        mapping = index.merge(local_citations)

        # Mapping preserves local order regardless of URL alphabetical order
        expected_mapping = {1: 1, 2: 2, 3: 3}
        assert mapping == expected_mapping


class TestCitationIndexMetadata:
    """Test metadata and tagging functionality."""

    def test_metadata_operations(self):
        """Test metadata get/set operations."""
        index = CitationIndex()

        # Add URL with metadata
        url = URL("https://example.com")

        index.add(url, title="Example Page", author="John Doe")

        # Retrieve metadata
        retrieved_metadata = index.get_metadata(url)
        assert retrieved_metadata == {"title": "Example Page", "author": "John Doe"}

        # Non-existent URL returns empty dict
        empty_metadata = index.get_metadata(URL("https://nonexistent.com"))
        assert empty_metadata == {}

    def test_tagging_operations(self):
        """Test tag management."""
        index = CitationIndex()

        # Add URL with tags
        url = URL("https://example.com")
        tags = ["research", "science", "example"]

        index.add(url, tags=tags)

        # Retrieve tags
        retrieved_tags = index.get_tags(url)
        assert retrieved_tags == set(tags)

        # Non-existent URL returns empty set
        empty_tags = index.get_tags(URL("https://nonexistent.com"))
        assert empty_tags == set()

    def test_find_by_tag(self):
        """Test finding citations by tag."""
        index = CitationIndex()

        # Add URLs with different tags
        url1 = URL("https://research.edu")
        url2 = URL("https://science.org")
        url3 = URL("https://news.com")

        index.add(url1, tags=["research", "academic"])
        index.add(url2, tags=["research", "science"])
        index.add(url3, tags=["news"])

        # Find by single tag
        research_indices = index.find_by_tag("research")
        assert len(research_indices) == 2

        # Should return list of indices
        assert 1 in research_indices  # url1
        assert 2 in research_indices  # url2

        # Verify we can look up the URLs by indices
        assert index.get_url(1) == url1
        assert index.get_url(2) == url2

        # Find by tag with single result
        news_indices = index.find_by_tag("news")
        assert len(news_indices) == 1
        assert news_indices[0] == 3  # url3 has index 3
        assert index.get_url(news_indices[0]) == url3

        # Find non-existent tag
        none_results = index.find_by_tag("nonexistent")
        assert len(none_results) == 0


class TestCitationIndexIterators:
    """Test iterator functionality."""

    def test_items_iterator(self):
        """Test items() iterator."""
        index = CitationIndex()

        # Add some URLs
        urls = [
            URL("https://example.com"),
            URL("https://test.org"),
            URL("https://research.edu"),
        ]

        for url in urls:
            index.add(url)

        # Iterate over items
        items = list(index.items())
        assert len(items) == 3

        # Should be (index, URL) tuples
        for idx, url in items:
            assert isinstance(idx, int)
            assert isinstance(url, URL)
            assert idx >= 1  # 1-based indexing

    def test_urls_iterator(self):
        """Test urls() iterator."""
        index = CitationIndex()

        urls = [URL("https://example.com"), URL("https://test.org")]

        for url in urls:
            index.add(url)

        # Iterate over URLs
        url_list = list(index.urls())
        assert len(url_list) == 2

        for url in url_list:
            assert isinstance(url, URL)

    def test_indices_iterator(self):
        """Test indices() iterator."""
        index = CitationIndex()

        # Add some URLs
        index.add(URL("https://example.com"))
        index.add(URL("https://test.org"))

        # Iterate over indices
        indices = list(index.indices())
        assert len(indices) == 2
        assert 1 in indices
        assert 2 in indices

    def test_len_and_contains(self):
        """Test __len__ and __contains__ operations."""
        index = CitationIndex()

        # Empty index
        assert len(index) == 0

        # Add URLs
        url1 = URL("https://example.com")
        url2 = URL("https://test.org")

        index.add(url1)
        assert len(index) == 1
        assert url1 in index
        assert url2 not in index

        index.add(url2)
        assert len(index) == 2
        assert url2 in index

        # Test canonicalized lookup
        url1_alt = URL("http://example.com")  # Different protocol
        index.add_alias(url1, url1_alt)
        assert url1_alt in index  # Should resolve through alias


class TestCitationIndexEdgeCases:
    """Test edge cases and error conditions."""

    def test_malformed_urls(self):
        """Test handling of malformed URLs."""
        index = CitationIndex()

        # URL that will canonicalize but is unusual
        unusual_url = "ftp://unusual-protocol.com"
        idx = index.add(URL(unusual_url))

        # Should still work, even with unusual protocol
        assert idx == 1
        assert len(index) == 1

        # Should be retrievable (may have trailing slash due to canonicalization)
        retrieved = index.get_url(1)
        assert str(retrieved) in (
            "ftp://unusual-protocol.com",
            "ftp://unusual-protocol.com/",
        )

    def test_circular_aliases(self):
        """Test circular alias resolution."""
        index = CitationIndex()

        # Add primary URL
        url1 = URL("https://example.com")
        url2 = URL("https://test.org")

        idx1 = index.add(url1)
        idx2 = index.add(url2)

        # Create circular alias (manually manipulate internal state for test)
        canonical1 = str(URL(url1).canonicalize())
        canonical2 = str(URL(url2).canonicalize())

        index.aliases[canonical1] = canonical2
        index.aliases[canonical2] = canonical1

        # Should handle gracefully (not infinite loop)
        result = index._resolve_aliases(canonical1)
        assert result in (canonical1, canonical2)  # Should stop somewhere

    def test_high_volume_operations(self):
        """Test performance with larger datasets."""
        index = CitationIndex()

        # Add many URLs
        urls = [URL(f"https://example{i}.com") for i in range(1000)]

        for i, url in enumerate(urls):
            idx = index.add(url)
            assert idx == i + 1  # Should be sequential

        assert len(index) == 1000

        # All should be retrievable
        for i, url in enumerate(urls):
            assert index.lookup(url) == i + 1
            assert index.get_url(i + 1) == url

    def test_unicode_urls(self):
        """Test handling of Unicode URLs."""
        index = CitationIndex()

        # Unicode domain and path
        unicode_url = URL("https://例え.テスト/パス?クエリ=値")
        idx = index.add(unicode_url)

        assert idx == 1
        retrieved = index.get_url(1)
        # URL should be preserved (though may be encoded)
        assert retrieved is not None


class TestCitationIndexIntegration:
    """Integration tests with realistic scenarios."""

    def test_realistic_research_scenario(self):
        """Test realistic research citation scenario."""
        index = CitationIndex()

        # Simulate research session with various sources
        research_urls = [
            URL("https://arxiv.org/abs/2304.12345"),
            URL("https://www.nature.com/articles/s41586-023-12345-6"),
            URL("https://pubmed.ncbi.nlm.nih.gov/12345678/"),
            URL("https://scholar.google.com/citations?user=ABC123"),
            URL("https://github.com/owner/repo/blob/main/paper.pdf"),
        ]

        # Add with realistic metadata and tags
        metadata_list = [
            {"title": "Large Language Models Paper", "year": 2024, "venue": "arXiv"},
            {"title": "Nature Research Article", "year": 2023, "venue": "Nature"},
            {"title": "Medical Study", "year": 2023, "venue": "PubMed"},
            {"title": "Author Profile", "type": "profile"},
            {"title": "Code Repository", "type": "code"},
        ]

        tag_list = [
            ["ai", "llm", "research"],
            ["science", "research", "peer-reviewed"],
            ["medical", "research", "peer-reviewed"],
            ["author", "profile"],
            ["code", "implementation"],
        ]

        # Add all citations
        for url, metadata, tags in zip(
            research_urls, metadata_list, tag_list, strict=False
        ):
            index.add(url, tags=tags, **metadata)

        # Verify all added correctly
        assert len(index) == 5

        # Test tag-based queries
        research_papers = index.find_by_tag("research")
        assert len(research_papers) == 3

        peer_reviewed = index.find_by_tag("peer-reviewed")
        assert len(peer_reviewed) == 2

        # Test metadata retrieval
        arxiv_metadata = index.get_metadata(research_urls[0])
        assert arxiv_metadata["venue"] == "arXiv"

        # Test merge with local citations (simulate message processing)
        message_citations = [
            research_urls[0],  # Existing
            URL("https://new-source.com"),  # New
            research_urls[2],  # Existing
        ]

        mapping = index.merge(message_citations)
        expected_mapping = {1: 1, 2: 6, 3: 3}  # Local -> Global
        assert mapping == expected_mapping

        # Should now have 6 total citations
        assert len(index) == 6
