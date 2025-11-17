from datetime import date, datetime, timedelta
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
    SearchQuery,
    SearchResult,
)


class MockDateProvider(BaseSearchProvider):
    """Mock provider that captures query dates for testing."""

    def __init__(self):
        super().__init__()
        self.name = "date_test"
        self.last_query = None
        self.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
            )
        ]

    async def search(self, query: SearchQuery, capability: ProviderCapability):
        """Capture the query for inspection."""
        self.last_query = query
        return [
            SearchResult(
                platform="test",
                id="1",
                url="https://test.com",
                content=f"Result with dates: {query.since} to {query.until}",
                content_type="text",
            )
        ]


class TestDateHandling:
    """Test suite for date handling in search."""

    @pytest.mark.asyncio
    async def test_explicit_date_range(self):
        """Test search with explicit since/until dates."""
        provider = MockDateProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Search with explicit dates
        since_date = date(2024, 1, 1)
        until_date = date(2024, 1, 31)

        await agent.tool_calls.invoke(
            "search",
            query="test",
            since=since_date,
            until=until_date,
        )

        # Check that dates were properly converted to datetime
        assert provider.last_query.since == datetime(2024, 1, 1, 0, 0, 0)
        assert provider.last_query.until == datetime(2024, 1, 31, 23, 59, 59, 999999)

    @pytest.mark.asyncio
    async def test_relative_time_windows(self):
        """Test last_day, last_week, last_month calculations."""
        provider = MockDateProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Set a specific date in context
        test_date = date(2024, 6, 15)
        agent.context["today"] = test_date

        # Test last_day
        await agent.tool_calls.invoke("search", query="test", timeframe="last_day")
        assert provider.last_query.since.date() == date(2024, 6, 14)
        assert provider.last_query.until.date() == date(2024, 6, 15)

        # Test last_week
        await agent.tool_calls.invoke("search", query="test", timeframe="last_week")
        assert provider.last_query.since.date() == date(2024, 6, 8)
        assert provider.last_query.until.date() == date(2024, 6, 15)

        # Test last_month
        await agent.tool_calls.invoke("search", query="test", timeframe="last_month")
        assert provider.last_query.since.date() == date(2024, 5, 16)
        assert provider.last_query.until.date() == date(2024, 6, 15)

    @pytest.mark.asyncio
    async def test_relative_windows_override_explicit_dates(self):
        """Test that relative windows override explicit dates."""
        provider = MockDateProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        agent.context["today"] = date(2024, 6, 15)

        # Provide both explicit dates and relative window
        await agent.tool_calls.invoke(
            "search",
            query="test",
            since=date(2024, 1, 1),
            until=date(2024, 12, 31),
            timeframe="last_week",  # Should override explicit dates
        )

        # Should use last_week, not explicit dates
        assert provider.last_query.since.date() == date(2024, 6, 8)
        assert provider.last_query.until.date() == date(2024, 6, 15)

    @pytest.mark.asyncio
    async def test_no_context_date_uses_today(self):
        """Test that missing context date defaults to today."""
        provider = MockDateProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Don't set context date
        await agent.tool_calls.invoke("search", query="test", timeframe="last_day")

        # Should use actual today
        today = date.today()
        yesterday = today - timedelta(days=1)

        assert provider.last_query.since.date() == yesterday
        assert provider.last_query.until.date() == today

    @pytest.mark.asyncio
    async def test_retroactive_execution(self):
        """Test retroactive execution by setting past context date."""
        provider = MockDateProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Set context to a past date
        past_date = date(2023, 3, 15)
        agent.context["today"] = past_date

        # Search last week from that past date
        await agent.tool_calls.invoke(
            "search", query="historical", timeframe="last_week"
        )

        # Should calculate from the past date
        assert provider.last_query.since.date() == date(2023, 3, 8)
        assert provider.last_query.until.date() == date(2023, 3, 15)


class TestQueryBuilding:
    """Test suite for query building and transformation."""

    @pytest.mark.asyncio
    async def test_basic_query_parameters(self):
        """Test basic query parameter handling."""
        provider = MockDateProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        await agent.tool_calls.invoke(
            "search",
            query="test query",
            limit=50,
            content_type="video",
            sort_by="recent",
        )

        query = provider.last_query
        assert query.text == "test query"
        assert query.limit == 50
        assert query.content_type == "video"
        assert query.sort_by == "recent"

    @pytest.mark.asyncio
    async def test_entity_search_query_building(self):
        """Test query building for entity search."""

        class EntityProvider(BaseSearchProvider):
            name = "entity_test"
            last_query = None
            capabilities = [
                ProviderCapability(
                    operation=OperationType.SEARCH,
                    domain=DataDomain.PEOPLE,
                    platform=None,
                )
            ]

            async def search(self, query, capability):
                self.last_query = query
                return [
                    SearchResult(
                        platform="test",
                        id="1",
                        url="https://test.com/person",
                        content="John Smith - CEO at TechCorp",
                        content_type="text",
                        author_name="John Smith",
                        author_handle="jsmith",
                    )
                ]

        provider = EntityProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Search with filters
        await agent.tool_calls.invoke(
            "search_entities",
            entity_type="person",
            name="John Smith",
            filters={"title": "CEO", "company": "TechCorp", "location": "NYC"},
        )

        # Check query was built correctly
        query = provider.last_query
        assert "John Smith" in query.text
        assert "title:CEO" in query.text
        assert "company:TechCorp" in query.text
        assert "location:NYC" in query.text

    @pytest.mark.asyncio
    async def test_platform_domain_selection(self):
        """Test that correct providers are selected based on platforms/domains."""

        web_provider = Mock(spec=BaseSearchProvider)
        web_provider.name = "web"
        web_provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=Platform.GOOGLE,
            )
        ]
        web_provider.search = AsyncMock(return_value=[])

        social_provider = Mock(spec=BaseSearchProvider)
        social_provider.name = "social"
        social_provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.SOCIAL_MEDIA,
                platform=Platform.TWITTER,
            )
        ]
        social_provider.search = AsyncMock(return_value=[])

        news_provider = Mock(spec=BaseSearchProvider)
        news_provider.name = "news"
        news_provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.NEWS,
                platform=None,
            )
        ]
        news_provider.search = AsyncMock(return_value=[])

        search = AgentSearch(
            auto_discover=False,
            providers=[web_provider, social_provider, news_provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Search specific platforms
        await agent.tool_calls.invoke(
            "search",
            query="test",
            platforms=["google", "twitter"],
        )

        # Should have called web and social providers
        web_provider.search.assert_called_once()
        social_provider.search.assert_called_once()
        news_provider.search.assert_not_called()

        # Reset mocks
        web_provider.search.reset_mock()
        social_provider.search.reset_mock()
        news_provider.search.reset_mock()

        # Search specific domains
        await agent.tool_calls.invoke(
            "search",
            query="test",
            domains=["news", "social_media"],
        )

        # Should have called news and social providers (both match the domains)
        # Platform-specific providers are still usable for domain searches
        web_provider.search.assert_not_called()
        social_provider.search.assert_called_once()  # Supports social_media domain
        news_provider.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_limit_handling(self):
        """Test that default limit is applied when not specified."""
        provider = MockDateProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
            default_limit=25,  # Custom default
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Search without specifying limit
        await agent.tool_calls.invoke("search", query="test")

        assert provider.last_query.limit == 25

        # Search with explicit limit
        await agent.tool_calls.invoke("search", query="test", limit=100)

        assert provider.last_query.limit == 100

    @pytest.mark.asyncio
    async def test_query_transformation(self):
        """Test provider-specific query transformation."""

        class CustomTransformProvider(BaseSearchProvider):
            name = "custom"
            last_transformed = None
            capabilities = [
                ProviderCapability(
                    operation=OperationType.SEARCH,
                    domain=DataDomain.WEB,
                    platform=None,
                )
            ]

            def transform_query(self, query: SearchQuery):
                """Custom transformation that adds prefix."""
                transformed = {
                    "q": f"site:example.com {query.text}",
                    "max_results": query.limit * 2,  # Double the limit
                    "order": "date" if query.sort_by == "recent" else "relevance",
                }
                self.last_transformed = transformed
                return transformed

            async def search(self, query, capability):
                # Transform would normally be called by provider
                self.transform_query(query)
                return []

        provider = CustomTransformProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        await agent.tool_calls.invoke(
            "search",
            query="test query",
            limit=10,
            sort_by="recent",
        )

        # Check transformation was applied
        assert provider.last_transformed["q"] == "site:example.com test query"
        assert provider.last_transformed["max_results"] == 20
        assert provider.last_transformed["order"] == "date"
