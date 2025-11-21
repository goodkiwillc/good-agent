import pytest
from good_agent import Agent
from good_agent.extensions.citations import CitationIndex, CitationManager


class TestCitationManagerInitialization:
    """Test manager initialization and installation."""

    @pytest.mark.asyncio
    async def test_manager_initialization_default(self):
        """Manager creates its own index by default."""
        manager = CitationManager()

        assert isinstance(manager.index, CitationIndex)
        assert len(manager.index) == 0

    @pytest.mark.asyncio
    async def test_manager_initialization_with_index(self):
        """Manager can use a provided index."""
        shared_index = CitationIndex()
        shared_index.add("https://example.com/doc1")

        manager = CitationManager(citation_index=shared_index)

        assert manager.index is shared_index
        assert len(manager.index) == 1

    @pytest.mark.asyncio
    async def test_manager_installation_on_agent(self):
        """Manager properly installs on an agent."""
        manager = CitationManager()
        async with Agent(extensions=[manager]) as agent:
            assert agent[CitationManager] is not None
            assert agent[CitationManager] is manager
            assert agent[CitationManager].agent is agent

            await agent.events.close()


class TestCitationManagerPublicAPI:
    """Test public API methods of CitationManager."""

    @pytest.mark.asyncio
    async def test_parse_markdown_format(self):
        """Parse method extracts citations from markdown."""
        manager = CitationManager()

        content = """
        Text with citations [1] and [2].

        [1]: https://example.com/source1
        [2]: https://example.com/source2
        """

        parsed, citations = manager.parse(content, content_format="markdown")

        assert "[1]" in parsed
        assert "[1]:" not in parsed  # Reference blocks removed
        assert len(citations) == 2
        assert "https://example.com/source1" in citations

    @pytest.mark.asyncio
    async def test_parse_llm_format(self):
        """Parse method can transform to LLM format."""
        manager = CitationManager()

        content = """
        Text with citations [1] and [2].

        [1]: https://example.com/source1
        [2]: https://example.com/source2
        """

        parsed, citations = manager.parse(content, content_format="llm")

        assert "[!CITE_1!]" in parsed
        assert "[!CITE_2!]" in parsed
        assert len(citations) == 2

    @pytest.mark.asyncio
    async def test_get_citations_count(self):
        """get_citations_count returns total citations."""
        manager = CitationManager()
        manager.index.add("https://example.com/doc1")
        manager.index.add("https://example.com/doc2")

        assert manager.get_citations_count() == 2

    @pytest.mark.asyncio
    async def test_get_citations_summary(self):
        """get_citations_summary returns formatted summary."""
        manager = CitationManager()
        manager.index.add("https://example.com/doc1")
        manager.index.add("https://example.com/doc2")

        summary = manager.get_citations_summary()

        assert "Citations (2 total)" in summary
        assert "[1] https://example.com/doc1" in summary
        assert "[2] https://example.com/doc2" in summary

    @pytest.mark.asyncio
    async def test_export_citations_json(self):
        """Export citations in JSON format."""
        manager = CitationManager()
        manager.index.add("https://example.com/doc1")

        export = manager.export_citations(format="json")

        assert '"total_citations": 1' in export
        assert "https://example.com/doc1" in export

    @pytest.mark.asyncio
    async def test_export_citations_markdown(self):
        """Export citations in markdown format."""
        manager = CitationManager()
        manager.index.add("https://example.com/doc1")

        export = manager.export_citations(format="markdown")

        assert "# Citations" in export
        assert "[https://example.com/doc1](https://example.com/doc1)" in export


class TestSharedIndexBehavior:
    """Test that multiple managers can share an index."""

    @pytest.mark.asyncio
    async def test_shared_index_across_managers(self):
        """Multiple managers can share the same global index."""
        shared_index = CitationIndex()

        manager1 = CitationManager(citation_index=shared_index)
        manager2 = CitationManager(citation_index=shared_index)

        # Add citation via manager1
        manager1.index.add("https://example.com/doc1")

        # Should be visible in manager2
        assert len(manager2.index) == 1
        assert manager2.index.lookup("https://example.com/doc1") == 1

    @pytest.mark.asyncio
    async def test_independent_managers_have_separate_indices(self):
        """Managers without shared index maintain separate state."""
        manager1 = CitationManager()
        manager2 = CitationManager()

        manager1.index.add("https://example.com/doc1")

        # Should NOT be visible in manager2
        assert len(manager2.index) == 0
        assert manager2.index.lookup("https://example.com/doc1") is None
