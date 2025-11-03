"""
Test suite for WebFetcher component tool registration.

Tests the specific tool registration behavior of the WebFetcher component
to ensure all tools are properly registered and functional.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from good_agent import Agent
from good_agent.extensions.citations import CitationManager
from good_agent.extensions.webfetcher import WebFetcher, WebFetchSummary
from goodintel_fetch.web import ExtractedContent, Request


class TestWebFetcherToolRegistration:
    """Test suite for WebFetcher component tool registration."""

    @pytest.mark.asyncio
    async def test_webfetcher_tools_registered_after_ready(self):
        """Test that all WebFetcher tools are registered after agent.ready()."""
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600)
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])

        # Tools should not be available before ready()
        assert len(agent.tools._tools) == 0

        await agent.ready()

        # All expected tools should be registered
        expected_tools = ["fetch", "fetch_many", "batch_fetch"]
        for tool_name in expected_tools:
            assert tool_name in agent.tools, f"Tool {tool_name} not registered"

        assert len(agent.tools._tools) == 3
        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_tool_signatures(self):
        """Test that WebFetcher tools have correct signatures."""
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600)
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])
        await agent.ready()

        # Test fetch tool signature
        fetch_tool = agent.tools["fetch"]
        signature = fetch_tool.signature
        params = signature["function"]["parameters"]["properties"]

        assert "url" in params
        assert params["url"]["type"] == "string"

        assert "format" in params
        # format is optional (anyOf string enum or null)
        assert "anyOf" in params["format"]

        assert "ttl" in params
        # ttl is optional (anyOf integer or null)
        assert "anyOf" in params["ttl"]

        assert "validate_content" in params
        # validate_content is optional (anyOf boolean or null)
        assert "anyOf" in params["validate_content"]
        assert params["validate_content"]["anyOf"][0]["type"] == "boolean"

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_fetch_tool_execution(self):
        """Test that the fetch tool can be executed."""
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600)
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])
        await agent.ready()

        # Mock the actual fetch functionality
        with patch("good_agent.extensions.webfetcher.fetch") as mock_fetch:
            # Create mock response
            mock_response = MagicMock()
            mock_response.url = "https://example.com"
            mock_response.title = "Test Page"
            mock_response.main = "Test content"
            mock_response.metadata = {"from_cache": False}

            # Mock the to() method to return ExtractedContent
            mock_request = Request(url="https://example.com")
            extracted = ExtractedContent(
                request=mock_request,
                url="https://example.com",
                status_code=200,
                title="Test Page",
                main="Test content",
            )
            mock_response.to = MagicMock(return_value=extracted)

            async def mock_fetch_gen(*args, **kwargs):
                yield mock_response

            mock_fetch.return_value = mock_fetch_gen()

            # Execute the tool
            fetch_tool = agent.tools["fetch"]
            result = await fetch_tool(
                _agent=agent,
                url="https://example.com",
                format="full",
                ttl=3600,
                validate_content=True,
            )

            assert result.success
            assert result.response is not None
            # Tool returns ExtractedContent object for format="full"
            assert isinstance(result.response, ExtractedContent)
            assert str(result.response.url).rstrip("/") == "https://example.com"
            assert result.response.title == "Test Page"
            assert result.response.main == "Test content"

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_fetch_with_summary_format(self):
        """Test that the fetch tool can return summaries."""
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600, enable_summarization=True)
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])
        await agent.ready()

        # Mock the fetch and summarization
        with patch("good_agent.extensions.webfetcher.fetch") as mock_fetch:
            mock_response = MagicMock()
            mock_response.url = "https://example.com"
            mock_response.title = "Test Page"
            mock_response.main = "Test content"
            mock_response.metadata = {"summary": "Test summary"}
            mock_response.author = None
            mock_response.published_date = None

            async def mock_fetch_gen(*args, **kwargs):
                yield mock_response

            mock_fetch.return_value = mock_fetch_gen()

            # Mock the summarization
            with patch.object(
                webfetcher, "_summarize_content", new_callable=AsyncMock
            ) as mock_summarize:
                mock_summarize.return_value = "Generated summary"

                # Execute the tool with summary format
                tool = agent.tools["fetch"]
                result = await tool(
                    _agent=agent,
                    url="https://example.com",
                    format="summary",
                    strategy="tldr",
                    word_limit=50,
                    ttl=3600,
                )

                assert result.success
                assert result.response is not None
                # Tool returns WebFetchSummary object for format="summary"
                assert isinstance(result.response, WebFetchSummary)
                # The summary will be from metadata["summary"] since it exists
                assert result.response.summary == "Test summary"

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_fetch_many_tool_execution(self):
        """Test that the fetch_many tool can be executed."""
        # Create agent with both CitationManager and WebFetcher
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600)
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])
        await agent.ready()

        # Mock the fetch functionality
        with patch("good_agent.extensions.webfetcher.fetch") as mock_fetch:
            mock_response1 = MagicMock()
            mock_response1.url = "https://example.com/1"
            mock_response1.title = "Page 1"
            mock_response1.main = "Content 1"
            mock_response1.metadata = {}
            mock_response1.request = MagicMock()
            mock_response1.request.url = "https://example.com/1"
            mock_request1 = Request(url="https://example.com/1")
            mock_response1.to = lambda cls: ExtractedContent(
                request=mock_request1,
                url="https://example.com/1",
                status_code=200,
                title="Page 1",
                main="Content 1",
            )

            mock_response2 = MagicMock()
            mock_response2.url = "https://example.com/2"
            mock_response2.title = "Page 2"
            mock_response2.main = "Content 2"
            mock_response2.metadata = {}
            mock_response2.request = MagicMock()
            mock_response2.request.url = "https://example.com/2"
            mock_request2 = Request(url="https://example.com/2")
            mock_response2.to = lambda cls: ExtractedContent(
                request=mock_request2,
                url="https://example.com/2",
                status_code=200,
                title="Page 2",
                main="Content 2",
            )

            async def mock_fetch_gen(*args, **kwargs):
                yield mock_response1
                yield mock_response2

            mock_fetch.return_value = mock_fetch_gen()

            # Execute the tool
            tool = agent.tools["fetch_many"]
            result = await tool(
                _agent=agent,
                urls=["https://example.com/1", "https://example.com/2"],
                format="full",
            )

            assert result.success
            assert result.response is not None
            # Tool returns list of ExtractedContent objects
            assert isinstance(result.response, list)
            assert len(result.response) == 2
            # Check that both results are present
            assert str(result.response[0].url).rstrip("/") == "https://example.com/1"
            assert str(result.response[1].url).rstrip("/") == "https://example.com/2"

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_tools_with_citation_manager_integration(self):
        """Test WebFetcher tool integration with CitationManager."""
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600)
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])
        await agent.ready()

        # Both components should be installed
        assert citation_manager._agent is agent
        assert webfetcher._agent is agent

        # Both tools should be available
        assert "fetch" in agent.tools
        assert "fetch_many" in agent.tools

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_without_citation_manager(self):
        """Test that WebFetcher works without CitationManager."""
        webfetcher = WebFetcher(default_ttl=3600)

        # WebFetcher should work fine without CitationManager
        agent = Agent("Web assistant", extensions=[webfetcher])
        await agent.ready()

        # Tools should be available
        assert "fetch" in agent.tools
        assert "fetch_many" in agent.tools

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_tool_error_handling(self):
        """Test that WebFetcher tools handle errors gracefully."""
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600)
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])
        await agent.ready()

        # Mock fetch to raise an exception
        with patch("good_agent.extensions.webfetcher.fetch") as mock_fetch:
            mock_fetch.side_effect = Exception("Fetch failed")

            # Execute the tool - should handle the error
            fetch_tool = agent.tools["fetch"]
            result = await fetch_tool(
                _agent=agent, url="https://invalid-url.com", format="full", ttl=3600
            )

            # Tool should return error response, not raise exception
            # Since fetch is mocked to raise an exception, the tool should handle it
            assert not result.success or result.error is not None

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_super_install_call(self):
        """Test that WebFetcher properly calls super().install()."""
        citation_manager = CitationManager()
        webfetcher = WebFetcher(default_ttl=3600)

        # Verify that the WebFetcher has component tools detected by metaclass
        assert hasattr(webfetcher, "_component_tools")
        assert len(webfetcher._component_tools) > 0

        # Create agent and wait for initialization
        agent = Agent("Web assistant", extensions=[citation_manager, webfetcher])
        await agent.ready()

        # Tools should be registered (confirming super().install() worked)
        assert len(agent.tools._tools) > 0

        # Check that webfetcher tools are registered
        expected_tools = ["fetch", "fetch_many", "batch_fetch"]
        for tool_name in expected_tools:
            assert tool_name in agent.tools

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_webfetcher_component_state_isolation(self):
        """Test that multiple WebFetcher instances maintain separate state."""
        citation_manager1 = CitationManager()
        citation_manager2 = CitationManager()
        webfetcher1 = WebFetcher(default_ttl=3600)
        webfetcher2 = WebFetcher(default_ttl=1800)

        agent1 = Agent("Assistant 1", extensions=[citation_manager1, webfetcher1])
        agent2 = Agent("Assistant 2", extensions=[citation_manager2, webfetcher2])

        await agent1.ready()
        await agent2.ready()

        # Both should have tools registered
        assert "fetch" in agent1.tools
        assert "fetch" in agent2.tools

        # Components should have different configurations
        from datetime import timedelta

        assert webfetcher1.default_ttl == timedelta(seconds=3600)
        assert webfetcher2.default_ttl == timedelta(seconds=1800)
        # Note: max_concurrent_fetches removed - fetch library handles concurrency

        # Components should reference different agents
        assert webfetcher1._agent is agent1
        assert webfetcher2._agent is agent2

        await agent1.async_close()
        await agent2.async_close()
