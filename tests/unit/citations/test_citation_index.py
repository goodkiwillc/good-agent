import pytest
from good_agent.extensions.citations import CitationIndex
from good_agent.core.types import URL


class TestCitationIndex:
    @pytest.mark.asyncio
    async def test_citation_index_initialization(self):
        citation_index = CitationIndex()
        assert citation_index.index_offset == 1
        assert len(citation_index) == 0
        assert citation_index.as_dict() == {}

    @pytest.mark.asyncio
    async def test_citation_index_add_and_retrieve(self):
        citation_index = CitationIndex()
        url1 = "https://example.com/doc1.pdf"
        url2 = "https://example.com/doc2.pdf"

        idx1 = citation_index.add(url1)
        idx2 = citation_index.add(url2)

        assert idx1 == 1
        assert idx2 == 2
        assert len(citation_index) == 2

        retrieved_idx1 = citation_index.lookup(url1)
        retrieved_idx2 = citation_index.lookup(url2)

        assert retrieved_idx1 == idx1
        assert retrieved_idx2 == idx2

        # Adding the same URL should return the same index
        idx1_again = citation_index.add(url1)
        assert idx1_again == idx1
        assert len(citation_index) == 2  # No duplicates
        other_idx = citation_index.lookup("https://nonexistent.com")
        assert other_idx is None

    def test_citation_index_aliases_metadata_and_tags(self):
        citation_index = CitationIndex()
        idx = citation_index.add(
            "https://example.com",
            value="Content",
            tags=["primary"],
            title="Example",
        )

        alias_idx = citation_index.add_alias(
            "https://example.com", "http://example.com"
        )
        assert alias_idx == idx
        assert citation_index.lookup("http://example.com") == idx
        assert citation_index.get_value("http://example.com") == "Content"

        citation_index.update_metadata(idx, title="Updated")
        metadata = citation_index.get_metadata(idx)
        assert metadata["title"] == "Updated"

        citation_index.remove_tag(idx, "primary")
        assert citation_index.get_tags(idx) == set()
        citation_index.add_tag(idx, ["alpha", "beta"])
        assert citation_index.find_by_tag("alpha") == [idx]

        mapping = citation_index.merge(["http://example.com"])
        assert mapping == {1: idx}

        entry = citation_index.get_entry(idx)
        assert entry[0] == URL("https://example.com")
        assert entry[1] == "Content"

        results = list(citation_index.get_entries_by_tag("beta"))
        assert results[0][0] == idx

        citation_index.aliases["https://alias.loop"] = "https://example.com"
        citation_index.aliases["https://cycle"] = "https://alias.loop"
        resolved = citation_index._resolve_aliases("https://cycle")
        assert isinstance(resolved, URL)
