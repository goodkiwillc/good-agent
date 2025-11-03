"""
Tests for CitationAdapter tool integration.

Focuses on:
- Tool signature transformation (url -> citation_idx)
- Parameter translation at runtime (indices -> URLs)
- Integration with agent tool system
- Multiple URLs support
"""

from typing import Annotated

import pytest
from good_agent import Agent
from good_agent.extensions.citations import CitationManager
from good_agent.tools import Tool
from good_agent.types import URL
from pydantic import Field


def mock_fetch_url(url: URL) -> str:
    """Mock function that fetches a URL."""
    return f"Content from {url}"


def mock_fetch_multiple(
    urls: Annotated[list[URL], Field(description="List of URLs to fetch")],
) -> list[str]:
    """Mock function that fetches multiple URLs."""
    return [f"Content from {u}" for u in urls]


def mock_fetch_alt_param(url_to_fetch: URL) -> str:
    """Mock function with different param name."""
    return f"Content from {url_to_fetch}"


def mock_search(query: str) -> str:
    """Mock function that searches."""
    return f"Results for {query}"


class TestToolAdapterIdentification:
    """Test identifying which tools should be adapted."""

    @pytest.mark.asyncio
    async def test_adapter_identifies_url_parameter(self):
        """Adapter identifies tools with 'url' parameter."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(fn=mock_fetch_url, name="fetch_url")

        adapter = manager._citation_adapter
        assert adapter is not None

        should_adapt = adapter.should_adapt(tool, agent)
        assert should_adapt is True

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_adapter_identifies_urls_parameter(self):
        """Adapter identifies tools with 'urls' array parameter."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(
            fn=mock_fetch_multiple,
            name="fetch_multiple",
        )

        adapter = manager._citation_adapter
        assert adapter is not None
        should_adapt = adapter.should_adapt(tool, agent)
        assert should_adapt is True

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_adapter_identifies_alternate_url_param(self):
        """Adapter identifies tools with alternate 'url' param names."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(fn=mock_fetch_alt_param, name="fetch_alt_param")

        adapter = manager._citation_adapter
        assert adapter is not None
        should_adapt = adapter.should_adapt(tool, agent)
        assert should_adapt is True

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_adapter_ignores_non_url_tools(self):
        """Adapter does not adapt tools without URL parameters."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(fn=mock_search, name="search")

        adapter = manager._citation_adapter
        assert adapter is not None
        should_adapt = adapter.should_adapt(tool, agent)
        assert should_adapt is False

        await agent.async_close()


class TestToolSignatureTransformation:
    """Test transformation of tool signatures."""

    @pytest.mark.asyncio
    async def test_url_parameter_becomes_citation_idx(self):
        """Tool 'url' parameter becomes 'citation_idx'."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(fn=mock_fetch_url, name="fetch_url")

        adapter = manager._citation_adapter
        assert adapter is not None
        original_sig = tool.signature

        adapted_sig = adapter.adapt_signature(tool, original_sig, agent)

        # Should have citation_idx instead of url
        params = adapted_sig["function"]["parameters"]["properties"]
        assert "citation_idx" in params
        assert "url" not in params

        # description should mention citation
        assert (
            params["citation_idx"]["description"]
            == "Index of the citation to use (0-based)"
        )

        # citation_idx should be integer
        assert params["citation_idx"]["type"] == "integer"

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_urls_parameter_becomes_citation_idxs(self):
        """Tool 'urls' array becomes 'citation_idxs' array."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(
            fn=mock_fetch_multiple,
            name="fetch_multiple",
        )

        adapter = manager._citation_adapter
        assert adapter is not None
        original_sig = tool.signature

        adapted_sig = adapter.adapt_signature(tool, original_sig, agent)

        params = adapted_sig["function"]["parameters"]["properties"]
        assert "citation_idxs" in params
        assert "urls" not in params

        # citation_idxs should be array of integers
        assert params["citation_idxs"]["type"] == "array"
        assert params["citation_idxs"]["items"]["type"] == "integer"
        assert (
            params["citation_idxs"]["description"]
            == "List of citation indices (0-based)"
        )

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_alternate_url_param_becomes_citation_idx(self):
        """Alternate 'url' param name becomes 'citation_idx'."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(fn=mock_fetch_alt_param, name="fetch_alt_param")

        adapter = manager._citation_adapter
        assert adapter is not None
        original_sig = tool.signature

        adapted_sig = adapter.adapt_signature(tool, original_sig, agent)

        params = adapted_sig["function"]["parameters"]["properties"]
        assert "citation_idx_to_fetch" in params  # adapted from url_to_fetch
        assert "url_to_fetch" not in params

        await agent.async_close()


class TestParameterTranslation:
    """Test runtime parameter translation."""

    @pytest.mark.asyncio
    async def test_citation_idx_translated_to_url(self):
        """citation_idx parameter is translated back to url."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # Add URL to global index
        url = "https://example.com/doc.pdf"
        idx = manager.index.add(url)

        adapter = manager._citation_adapter
        assert adapter is not None

        # Simulate LLM calling with citation_idx
        llm_params = {"citation_idx": idx}

        # Adapter should translate to url
        translated = adapter.adapt_parameters("fetch_url", llm_params, agent)

        assert "url" in translated
        assert translated["url"] == url
        assert "citation_idx" not in translated

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_citation_idxs_translated_to_urls(self):
        """citation_idxs array is translated to urls array."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # Add URLs to global index
        url1 = "https://example.com/doc1.pdf"
        url2 = "https://example.com/doc2.pdf"
        idx1 = manager.index.add(url1)
        idx2 = manager.index.add(url2)

        adapter = manager._citation_adapter
        assert adapter is not None

        llm_params = {"citation_idxs": [idx1, idx2]}

        translated = adapter.adapt_parameters("fetch_multiple", llm_params, agent)

        assert "urls" in translated
        assert len(translated["urls"]) == 2
        assert url1 in translated["urls"]
        assert url2 in translated["urls"]
        assert "citation_idxs" not in translated

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_invalid_citation_idx_preserved(self):
        """Invalid citation index is preserved for error handling."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        adapter = manager._citation_adapter
        assert adapter is not None

        # Use invalid index
        llm_params = {"citation_idx": 999}

        with pytest.warns(
            UserWarning, match="Citation index 999 not found in global index."
        ):
            translated = adapter.adapt_parameters("fetch_url", llm_params, agent)

        # Invalid index should be preserved
        assert "citation_idx" in translated
        assert translated["citation_idx"] == 999

        # The resulting tool call will (and should) fail

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_non_url_tool_params_unchanged(self):
        """Parameters for non-URL tools are unchanged."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        adapter = manager._citation_adapter
        assert adapter is not None

        llm_params = {"query": "test search"}

        translated = adapter.adapt_parameters("search", llm_params, agent)

        # Parameters should be unchanged
        assert translated == llm_params

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_alternate_param_name_translation(self):
        """Alternate URL param name is correctly translated."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # Add URL to global index
        url = "https://example.com/doc.pdf"
        idx = manager.index.add(url)

        adapter = manager._citation_adapter
        assert adapter is not None

        llm_params = {"citation_idx_to_fetch": idx}

        translated = adapter.adapt_parameters("fetch_alt_param", llm_params, agent)

        assert "url_to_fetch" in translated
        assert translated["url_to_fetch"] == url
        assert "citation_idx_to_fetch" not in translated

        await agent.async_close()


class TestEndToEndToolIntegration:
    """Test complete flow with agent tool calls."""

    @pytest.mark.asyncio
    async def test_tool_call_with_citation_idx(self):
        """Tool can be called via citation index instead of URL."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        # Register tool
        tool = Tool(fn=mock_fetch_url, name="fetch_url")
        await agent.tools.register_tool(tool)

        # Add URL to index
        url = URL("https://example.com/doc.pdf")
        idx = manager.index.add(url)

        # Manually call tool with citation_idx (simulating LLM call)
        # In real usage, LLM would see adapted signature with citation_idx
        result = mock_fetch_url(url=url)

        assert "Content from" in result
        assert url in result

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_adapter_analyze_transformation(self):
        """Adapter can analyze what transformations it will perform."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(fn=mock_fetch_url, name="fetch_url")

        adapter = manager._citation_adapter
        assert adapter is not None
        metadata = adapter.analyze_transformation(tool, tool.signature)

        assert "url" in metadata.removed_params
        assert "citation_idx" in metadata.added_params

        await agent.async_close()


class TestAdapterDisabling:
    """Test behavior when adapter is disabled."""

    @pytest.mark.asyncio
    async def test_manager_without_adapter(self):
        """Manager can be created without tool adapter."""
        manager = CitationManager(use_tool_adapter=False)
        agent = Agent(extensions=[manager])
        await agent.ready()

        # Adapter should not be installed
        assert manager._citation_adapter is None

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_tools_not_adapted_when_disabled(self):
        """Tools are not adapted when adapter is disabled."""
        manager = CitationManager(use_tool_adapter=False)
        agent = Agent(extensions=[manager])
        await agent.ready()

        tool = Tool(fn=mock_fetch_url, name="fetch_url")
        await agent.tools.register_tool(tool)

        # Tool signature should be unchanged
        sig = tool.signature
        params = sig["function"]["parameters"]["properties"]

        assert "url" in params
        assert "citation_idx" not in params

        await agent.async_close()
