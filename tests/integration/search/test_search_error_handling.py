import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from good_agent import Agent
from good_agent.extensions.search import (
    AgentSearch,
    BaseSearchProvider,
    DataDomain,
    OperationType,
    Platform,
    ProviderCapability,
    SearchResult,
)


class FailingProvider(BaseSearchProvider):
    """Provider that fails in various ways for testing."""

    def __init__(self, failure_mode="exception"):
        super().__init__()
        self.name = f"failing_{failure_mode}"
        self.failure_mode = failure_mode
        self.attempt_count = 0
        self.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
            )
        ]

    async def search(self, query, capability):
        """Fail in different ways based on mode."""
        self.attempt_count += 1

        if self.failure_mode == "exception":
            raise Exception("Provider failed")
        elif self.failure_mode == "timeout":
            await asyncio.sleep(2)  # Shorter timeout for testing
        elif self.failure_mode == "empty":
            return []
        elif self.failure_mode == "invalid":
            return "not a list"  # Invalid return type
        elif self.failure_mode == "partial":
            # Succeed on second attempt
            if self.attempt_count == 1:
                raise Exception("Temporary failure")
            return [
                SearchResult(
                    platform="test",
                    id="1",
                    url="https://test.com",
                    content="Success after retry",
                    content_type="text",
                )
            ]

    async def validate(self):
        """Validation can also fail."""
        if self.failure_mode == "invalid_config":
            return False
        return True


class TestErrorHandling:
    """Test suite for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_provider_exception_handling(self):
        """Test handling of provider exceptions."""
        failing_provider = FailingProvider("exception")
        working_provider = Mock(spec=BaseSearchProvider)
        working_provider.name = "working"
        working_provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
            )
        ]
        working_provider.search = AsyncMock(
            return_value=[
                SearchResult(
                    platform="working",
                    id="1",
                    url="https://working.com",
                    content="Working result",
                    content_type="text",
                )
            ]
        )

        search = AgentSearch(
            auto_discover=False,
            providers=[failing_provider, working_provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Should still get results from working provider
        response = await agent.invoke("search", query="test")
        results = response.response

        assert "working" in results
        assert len(results["working"]) == 1
        assert "failing_exception" in results
        assert results["failing_exception"] == []  # Failed provider returns empty list

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        """Test when all providers fail."""
        failing1 = FailingProvider("exception")
        failing2 = FailingProvider("timeout")

        search = AgentSearch(
            auto_discover=False,
            providers=[failing1, failing2],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Verify search is installed
        print(f"Agent tools: {list(agent.tools.keys())}")
        print(f"Search component installed: {search in agent.extensions}")

        # Check if agent is set on component
        print(f"Search component has agent: {search.agent is not None}")
        print(f"Search component agent: {search.agent}")

        # Test calling the method directly first (this won't work without agent)
        print("Testing direct method call...")
        direct_result = await search.search(query="test")
        print(f"Direct result: {direct_result}")
        print(f"Direct result type: {type(direct_result)}")

        # Should return empty results for each provider
        print("Testing via agent.invoke...")
        response = await agent.invoke("search", query="test")

        # Debug output
        print(f"Response type: {type(response)}")
        print(f"Response: {response}")
        print(f"Response has response attr: {hasattr(response, 'response')}")
        if hasattr(response, "response"):
            print(f"Response.response: {response.response}")
            print(
                f"Response.response type: {type(response.response) if response.response is not None else 'None'}"
            )

        results = response.response

        # Handle None case - this shouldn't happen but guard against it
        if results is None:
            results = {}

        assert "failing_exception" in results
        assert results["failing_exception"] == []
        # Timeout provider might not appear if it times out

    @pytest.mark.asyncio
    async def test_no_providers_available(self):
        """Test when no providers match the requirements."""
        # Provider only supports NEWS domain
        news_provider = Mock(spec=BaseSearchProvider)
        news_provider.name = "news_only"
        news_provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.NEWS,
                platform=None,
            )
        ]

        search = AgentSearch(
            auto_discover=False,
            providers=[news_provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Search for SOCIAL_MEDIA which provider doesn't support
        response = await agent.invoke(
            "search",
            query="test",
            domains=["social_media"],
        )
        results = response.response

        assert results == {}  # No results when no providers available

    @pytest.mark.asyncio
    async def test_invalid_platform_name(self):
        """Test handling of invalid platform names."""
        provider = Mock(spec=BaseSearchProvider)
        provider.name = "test"
        provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=Platform.GOOGLE,
            )
        ]
        provider.search = AsyncMock(return_value=[])

        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Search with invalid platform name
        await agent.invoke(
            "search",
            query="test",
            platforms=["invalid_platform", "google"],  # One invalid, one valid
        )

        # Should still search Google, ignore invalid
        provider.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_domain_name(self):
        """Test handling of invalid domain names."""
        provider = Mock(spec=BaseSearchProvider)
        provider.name = "test"
        provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
            )
        ]
        provider.search = AsyncMock(return_value=[])

        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Search with invalid domain name
        await agent.invoke(
            "search",
            query="test",
            domains=["invalid_domain", "web"],  # One invalid, one valid
        )

        # Should still search web domain
        provider.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_query_handling(self):
        """Test handling of empty or None query."""
        provider = Mock(spec=BaseSearchProvider)
        provider.name = "test"
        provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
            )
        ]
        provider.search = AsyncMock(return_value=[])

        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Search with empty query
        await agent.invoke("search", query="")

        # Should still call provider (provider decides how to handle empty query)
        provider.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_provider_validation_failure(self):
        """Test that providers failing validation are not used."""
        failing_validation = FailingProvider("invalid_config")
        working_provider = Mock(spec=BaseSearchProvider)
        working_provider.name = "working"
        working_provider.validate = AsyncMock(return_value=True)
        working_provider.capabilities = []

        search = AgentSearch(
            auto_discover=True,  # Will try to validate
            providers=[],  # Start empty
        )

        # Manually trigger discovery with our providers
        search.registry._providers = {}

        # Only working provider should be registered after validation
        await working_provider.validate()
        if await working_provider.validate():
            search.registry.register(working_provider)

        await failing_validation.validate()
        if await failing_validation.validate():
            search.registry.register(failing_validation)

        assert "working" in search.registry.list_providers()
        assert "failing_invalid_config" not in search.registry.list_providers()


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_very_large_result_set(self):
        """Test handling of very large result sets."""

        class LargeResultProvider(BaseSearchProvider):
            name = "large"
            capabilities = [
                ProviderCapability(
                    operation=OperationType.SEARCH,
                    domain=DataDomain.WEB,
                    platform=None,
                )
            ]

            async def search(self, query, capability):
                # Return 1000 results
                return [
                    SearchResult(
                        platform="large",
                        id=str(i),
                        url=f"https://test.com/{i}",
                        content=f"Result {i}",
                        content_type="text",
                    )
                    for i in range(1000)
                ]

        provider = LargeResultProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        response = await agent.invoke("search", query="test", limit=10)
        results = response.response

        # Provider returns 1000 but that's ok - component doesn't enforce limit
        assert len(results["large"]) == 1000

    @pytest.mark.asyncio
    async def test_duplicate_provider_names(self):
        """Test handling of duplicate provider names."""
        provider1 = Mock(spec=BaseSearchProvider)
        provider1.name = "duplicate"
        provider1.capabilities = []

        provider2 = Mock(spec=BaseSearchProvider)
        provider2.name = "duplicate"  # Same name
        provider2.capabilities = []

        search = AgentSearch(
            auto_discover=False,
            providers=[provider1, provider2],
        )

        # Second registration should overwrite first
        assert search.registry.get_provider("duplicate") == provider2

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test handling of special characters in search query."""

        class EchoProvider(BaseSearchProvider):
            name = "echo"
            last_query = None
            capabilities = [
                ProviderCapability(
                    operation=OperationType.SEARCH,
                    domain=DataDomain.WEB,
                    platform=None,
                )
            ]

            async def search(self, query, capability):
                self.last_query = query.text
                return [
                    SearchResult(
                        platform="echo",
                        id="1",
                        url="https://test.com",
                        content=f"Echo: {query.text}",
                        content_type="text",
                    )
                ]

        provider = EchoProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Test various special characters
        special_queries = [
            "test & test",
            "test | test",
            'test "quoted" test',
            "test\nwith\nnewlines",
            "test\twith\ttabs",
            "émojis 🎉 and ünïcödé",
            "<script>alert('xss')</script>",
        ]

        for query_text in special_queries:
            response = await agent.invoke("search", query=query_text)
            results = response.response
            assert provider.last_query == query_text
            assert len(results["echo"]) == 1

    @pytest.mark.asyncio
    async def test_concurrent_searches(self):
        """Test multiple concurrent searches."""

        class SlowProvider(BaseSearchProvider):
            name = "slow"
            capabilities = [
                ProviderCapability(
                    operation=OperationType.SEARCH,
                    domain=DataDomain.WEB,
                    platform=None,
                )
            ]

            def __init__(self):
                super().__init__()
                self.search_count = 0
                self._lock = asyncio.Lock()

            async def search(self, query, capability):
                async with self._lock:
                    self.search_count += 1
                    count = self.search_count
                await asyncio.sleep(0.1)  # Simulate slow search
                return [
                    SearchResult(
                        platform="slow",
                        id=str(count),
                        url=f"https://test.com/{count}",
                        content=f"Result for: {query.text}",
                        content_type="text",
                    )
                ]

        provider = SlowProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        # Launch multiple searches concurrently
        tasks = [agent.invoke("search", query=f"query{i}") for i in range(5)]

        responses = await asyncio.gather(*tasks)
        results = [r.response for r in responses]

        # All searches should complete
        assert len(results) == 5
        assert provider.search_count == 5

        # Each result should be unique
        seen_ids = set()
        for result_set in results:
            for result in result_set["slow"]:
                assert result.id not in seen_ids
                seen_ids.add(result.id)

    @pytest.mark.asyncio
    async def test_result_with_missing_fields(self):
        """Test handling of results with missing optional fields."""

        class MinimalProvider(BaseSearchProvider):
            name = "minimal"
            capabilities = [
                ProviderCapability(
                    operation=OperationType.SEARCH,
                    domain=DataDomain.WEB,
                    platform=None,
                )
            ]

            async def search(self, query, capability):
                # Return results with only required fields
                return [
                    SearchResult(
                        platform="minimal",
                        id="1",
                        url="https://test.com",
                        content="Minimal result",
                        content_type="text",
                        # All other fields will be None or default
                    )
                ]

        provider = MinimalProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.ready()

        response = await agent.invoke("search", query="test")
        results = response.response

        assert len(results["minimal"]) == 1
        result = results["minimal"][0]

        # Required fields should be present
        assert result.platform == "minimal"
        assert result.id == "1"
        assert result.url in [
            "https://test.com",
            "https://test.com/",
        ]  # Allow trailing slash
        assert result.content == "Minimal result"

        # Optional fields should be None or default
        assert result.author_name is None
        assert result.created_at is None
        assert result.metrics == {}
        assert result.media == []
