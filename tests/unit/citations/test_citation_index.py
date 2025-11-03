import pytest
from good_agent.extensions.citations import CitationIndex


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
