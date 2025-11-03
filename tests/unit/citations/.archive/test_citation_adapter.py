"""
Unit tests for the CitationAdapter tool adapter.

Tests cover:
- Strict parameter matching (url, urls only)
- Signature transformation
- Parameter transformation
- Integration with CitationManager
"""

from unittest.mock import MagicMock

import pytest
from good_agent import Agent, tool
from good_agent.extensions.citations import CitationManager
from good_agent.extensions.citations.citation_adapter import CitationAdapter


# Test tools with different parameter configurations
@tool
async def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch content from a URL."""
    return f"Content from {url}"


@tool
async def fetch_urls(urls: list[str], parallel: bool = True) -> list[str]:
    """Fetch multiple URLs."""
    return [f"Content from {u}" for u in urls]


@tool
async def fetch_link(link: str) -> str:
    """Fetch from a link (should NOT be adapted - wrong param name)."""
    return f"Content from {link}"


@tool
async def process_url_data(url_data: str) -> str:
    """Process URL data (should NOT be adapted - not exact 'url')."""
    return f"Processed {url_data}"


@tool
async def search_web(query: str, source_url: str | None = None) -> str:
    """Search with optional source URL (should NOT be adapted - not exact 'url')."""
    return f"Results for {query}"


@tool
async def no_url_tool(data: str, count: int) -> str:
    """Tool without URL parameters."""
    return f"Processed {data}"


class TestCitationAdapterMatching:
    """Test the strict should_adapt logic."""

    def test_adapts_single_url_parameter(self):
        """Test adapter matches tools with 'url: str' parameter."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Should adapt fetch_url (has url: str)
        assert adapter.should_adapt(fetch_url, agent) is True

    def test_adapts_urls_list_parameter(self):
        """Test adapter matches tools with 'urls: list[str]' parameter."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Should adapt fetch_urls (has urls: list[str])
        assert adapter.should_adapt(fetch_urls, agent) is True

    def test_does_not_adapt_link_parameter(self):
        """Test adapter does NOT match 'link' parameter."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Should NOT adapt fetch_link (param is 'link', not 'url')
        assert adapter.should_adapt(fetch_link, agent) is False

    def test_does_not_adapt_url_prefix_parameter(self):
        """Test adapter does NOT match 'url_data' or 'source_url'."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Should NOT adapt - parameter is 'url_data', not 'url'
        assert adapter.should_adapt(process_url_data, agent) is False

        # Should NOT adapt - parameter is 'source_url', not 'url'
        assert adapter.should_adapt(search_web, agent) is False

    def test_does_not_adapt_no_url_tool(self):
        """Test adapter does NOT match tools without URL parameters."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Should NOT adapt - no URL parameters
        assert adapter.should_adapt(no_url_tool, agent) is False


class TestCitationAdapterTransformation:
    """Test signature and parameter transformations."""

    def test_single_url_signature_transformation(self):
        """Test transforming url: str to citation_idx: int."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        original_sig = fetch_url.signature
        adapted_sig = adapter.adapt_signature(fetch_url, original_sig, agent)

        params = adapted_sig["function"]["parameters"]["properties"]

        # Check url was replaced with citation_idx
        assert "url" not in params
        assert "citation_idx" in params
        assert params["citation_idx"]["type"] == "integer"
        assert params["citation_idx"]["minimum"] == 0

        # Check other params unchanged
        assert "timeout" in params
        assert params["timeout"]["type"] == "integer"

        # Check required list was updated
        required = adapted_sig["function"]["parameters"].get("required", [])
        assert "url" not in required
        assert "citation_idx" in required

    def test_urls_list_signature_transformation(self):
        """Test transforming urls: list[str] to citation_idxs: list[int]."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        original_sig = fetch_urls.signature
        adapted_sig = adapter.adapt_signature(fetch_urls, original_sig, agent)

        params = adapted_sig["function"]["parameters"]["properties"]

        # Check urls was replaced with citation_idxs
        assert "urls" not in params
        assert "citation_idxs" in params
        assert params["citation_idxs"]["type"] == "array"
        assert params["citation_idxs"]["items"]["type"] == "integer"

        # Check other params unchanged
        assert "parallel" in params

    def test_single_url_parameter_transformation(self):
        """Test converting citation_idx back to URL."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Add some citations to the index
        manager.index.add("https://example.com", value="Example")
        manager.index.add("https://test.com", value="Test")

        # Simulate LLM providing citation index
        params_from_llm = {"citation_idx": 1, "timeout": 10}

        # Transform back to URL
        adapted_params = adapter.adapt_parameters("fetch_url", params_from_llm, agent)

        assert "citation_idx" not in adapted_params
        assert "url" in adapted_params
        assert str(adapted_params["url"]).rstrip("/") == "https://example.com"
        assert adapted_params["timeout"] == 10

    def test_urls_list_parameter_transformation(self):
        """Test converting citation_idxs list back to URLs."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Add citations
        idx1 = manager.index.add("https://example.com")
        idx2 = manager.index.add("https://test.com")
        idx3 = manager.index.add("https://demo.com")

        # Simulate LLM providing citation indices
        params_from_llm = {"citation_idxs": [idx1, idx3], "parallel": False}

        # Transform back to URLs
        adapted_params = adapter.adapt_parameters("fetch_urls", params_from_llm, agent)

        assert "citation_idxs" not in adapted_params
        assert "urls" in adapted_params
        assert len(adapted_params["urls"]) == 2
        assert str(adapted_params["urls"][0]).rstrip("/") == "https://example.com"
        assert str(adapted_params["urls"][1]).rstrip("/") == "https://demo.com"
        assert adapted_params["parallel"] is False

    def test_invalid_citation_index_handling(self):
        """Test handling of invalid citation indices."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Only one citation exists
        manager.index.add("https://example.com")

        # Try with invalid index
        params_from_llm = {"citation_idx": 999, "timeout": 10}
        adapted_params = adapter.adapt_parameters("fetch_url", params_from_llm, agent)

        # Should keep the invalid index (let tool handle the error)
        assert "citation_idx" in adapted_params
        assert adapted_params["citation_idx"] == 999
        assert "url" not in adapted_params

    def test_mixed_valid_invalid_indices(self):
        """Test list with mix of valid and invalid indices."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        # Add some citations
        idx1 = manager.index.add("https://example.com")
        idx2 = manager.index.add("https://test.com")

        # Mix of valid and invalid indices
        params_from_llm = {"citation_idxs": [idx1, 999, idx2], "parallel": True}
        adapted_params = adapter.adapt_parameters("fetch_urls", params_from_llm, agent)

        # Should convert valid ones, keep invalid as-is
        assert "urls" in adapted_params
        assert len(adapted_params["urls"]) == 2  # Only valid ones
        assert str(adapted_params["urls"][0]).rstrip("/") == "https://example.com"
        assert str(adapted_params["urls"][1]).rstrip("/") == "https://test.com"


class TestCitationAdapterMetadata:
    """Test adapter metadata for conflict detection."""

    def test_analyze_transformation_single_url(self):
        """Test metadata analysis for single URL transformation."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)

        signature = fetch_url.signature
        metadata = adapter.analyze_transformation(fetch_url, signature)

        # Should report removing 'url' and adding 'citation_idx'
        assert "url" in metadata.removed_params
        assert "citation_idx" in metadata.added_params
        assert len(metadata.modified_params) == 0

    def test_analyze_transformation_urls_list(self):
        """Test metadata analysis for URLs list transformation."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)

        signature = fetch_urls.signature
        metadata = adapter.analyze_transformation(fetch_urls, signature)

        # Should report removing 'urls' and adding 'citation_idxs'
        assert "urls" in metadata.removed_params
        assert "citation_idxs" in metadata.added_params
        assert len(metadata.modified_params) == 0

    def test_analyze_transformation_no_match(self):
        """Test metadata when no transformation needed."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)

        signature = no_url_tool.signature
        metadata = adapter.analyze_transformation(no_url_tool, signature)

        # Should report no changes
        assert len(metadata.removed_params) == 0
        assert len(metadata.added_params) == 0
        assert len(metadata.modified_params) == 0


@pytest.mark.asyncio
class TestCitationAdapterIntegration:
    """Test integration with Agent and CitationManager."""

    async def test_with_citation_manager(self):
        """Test CitationAdapter working with CitationManager."""
        # Create manager with adapter
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        manager.register_tool_adapter(adapter)

        # Create agent
        agent = Agent("Test agent", tools=[fetch_url, fetch_urls], extensions=[manager])
        await agent.ready()

        # Add some citations
        idx1 = manager.index.add("https://example.com", value="Example Site")
        idx2 = manager.index.add("https://test.com", value="Test Site")

        # What the LLM sees: fetch_url(citation_idx: int, timeout: int)
        # Simulate the transformation that would happen
        params_from_llm = {"citation_idx": idx1, "timeout": 5}
        adapted = adapter.adapt_parameters("fetch_url", params_from_llm, agent)

        assert str(adapted["url"]).rstrip("/") == "https://example.com"
        assert adapted["timeout"] == 5

    async def test_description_updated(self):
        """Test that tool descriptions mention citation usage."""
        manager = CitationManager()
        adapter = CitationAdapter(manager)
        agent = MagicMock()

        original_sig = fetch_url.signature
        adapted_sig = adapter.adapt_signature(fetch_url, original_sig, agent)

        # Check description was updated
        description = adapted_sig["function"]["description"]
        assert "citation" in description.lower()
        assert "index" in description.lower()


@pytest.mark.asyncio
async def test_end_to_end_citation_flow():
    """Test complete flow with CitationAdapter."""

    # Create manager and populate citations
    manager = CitationManager()

    # Pre-populate with some URLs
    idx1 = manager.index.add("https://arxiv.org/paper1.pdf", value="Paper 1")
    idx2 = manager.index.add("https://github.com/repo", value="Repository")
    idx3 = manager.index.add("https://docs.example.com", value="Documentation")

    # Register adapter
    adapter = CitationAdapter(manager)
    manager.register_tool_adapter(adapter)

    # Create agent
    agent = Agent(
        "Research assistant that uses citations",
        tools=[fetch_url, fetch_urls],
        extensions=[manager],
    )
    await agent.ready()

    # Verify tools are registered
    assert "fetch_url" in agent.tools
    assert "fetch_urls" in agent.tools

    # What the LLM would see:
    # - fetch_url(citation_idx: int, timeout: int)
    # - fetch_urls(citation_idxs: list[int], parallel: bool)

    # Simulate LLM calling with citation indices
    single_params = {"citation_idx": idx1, "timeout": 10}
    adapted_single = adapter.adapt_parameters("fetch_url", single_params, agent)
    assert str(adapted_single["url"]).rstrip("/") == "https://arxiv.org/paper1.pdf"

    multi_params = {"citation_idxs": [idx2, idx3], "parallel": True}
    adapted_multi = adapter.adapt_parameters("fetch_urls", multi_params, agent)
    assert len(adapted_multi["urls"]) == 2
    assert str(adapted_multi["urls"][0]).rstrip("/") == "https://github.com/repo"
    assert str(adapted_multi["urls"][1]).rstrip("/") == "https://docs.example.com"
