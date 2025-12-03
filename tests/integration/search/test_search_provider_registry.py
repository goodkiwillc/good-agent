from typing import Literal
from unittest.mock import AsyncMock, Mock

import pytest

from good_agent.extensions.search import (
    DataDomain,
    OperationType,
    Platform,
    ProviderCapability,
    SearchConstraints,
    SearchProviderRegistry,
)


class TestSearchProviderRegistry:
    """Test suite for SearchProviderRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return SearchProviderRegistry()

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider with test capabilities."""
        provider = Mock()
        provider.name = "test_provider"
        provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=Platform.GOOGLE,
                method="web_search",
                data_freshness=0,
                data_completeness=0.9,
                rate_limit=100,
                cost_per_request=0.002,
            )
        ]
        provider.validate = AsyncMock(return_value=True)
        return provider

    def test_register_provider(self, registry, mock_provider):
        """Test basic provider registration."""
        registry.register(mock_provider)

        assert "test_provider" in registry.list_providers()
        assert registry.get_provider("test_provider") == mock_provider

    def test_unregister_provider(self, registry, mock_provider):
        """Test provider unregistration."""
        registry.register(mock_provider)
        assert "test_provider" in registry.list_providers()

        registry.unregister("test_provider")
        assert "test_provider" not in registry.list_providers()
        assert registry.get_provider("test_provider") is None

    def test_find_capable_providers_exact_match(self, registry):
        """Test finding providers with exact capability match."""
        # Create providers with different capabilities
        web_provider = Mock()
        web_provider.name = "web"
        web_provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=Platform.GOOGLE,
            )
        ]

        social_provider = Mock()
        social_provider.name = "social"
        social_provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.SOCIAL_MEDIA,
                platform=Platform.TWITTER,
            )
        ]

        registry.register(web_provider)
        registry.register(social_provider)

        # Find web search providers
        web_providers = registry.find_capable_providers(
            OperationType.SEARCH, DataDomain.WEB, Platform.GOOGLE
        )
        assert len(web_providers) == 1
        assert web_providers[0].name == "web"

        # Find social media providers
        social_providers = registry.find_capable_providers(
            OperationType.SEARCH, DataDomain.SOCIAL_MEDIA, Platform.TWITTER
        )
        assert len(social_providers) == 1
        assert social_providers[0].name == "social"

    def test_find_capable_providers_cross_platform(self, registry):
        """Test finding cross-platform providers."""
        # Provider that works across all platforms
        cross_platform = Mock()
        cross_platform.name = "universal"
        cross_platform.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,  # Works for any platform
            )
        ]

        # Platform-specific provider
        specific = Mock()
        specific.name = "google_only"
        specific.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=Platform.GOOGLE,
            )
        ]

        registry.register(cross_platform)
        registry.register(specific)

        # Search for Google should return both
        providers = registry.find_capable_providers(
            OperationType.SEARCH, DataDomain.WEB, Platform.GOOGLE
        )
        assert len(providers) == 2
        assert {p.name for p in providers} == {"universal", "google_only"}

        # Search for Bing should only return universal
        providers = registry.find_capable_providers(
            OperationType.SEARCH, DataDomain.WEB, Platform.BING
        )
        assert len(providers) == 1
        assert providers[0].name == "universal"

    def test_get_best_provider_no_constraints(self, registry):
        """Test provider selection without constraints returns first available."""
        provider1 = Mock()
        provider1.name = "first"
        provider1.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
            )
        ]

        provider2 = Mock()
        provider2.name = "second"
        provider2.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
            )
        ]

        registry.register(provider1)
        registry.register(provider2)

        best = registry.get_best_provider(OperationType.SEARCH, DataDomain.WEB)
        assert best.name == "first"  # Returns first when no constraints

    def test_get_best_provider_cost_constraint(self, registry):
        """Test provider selection with cost constraints."""
        expensive = Mock()
        expensive.name = "expensive"
        expensive.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
                cost_per_request=0.01,
                data_completeness=0.95,
            )
        ]

        cheap = Mock()
        cheap.name = "cheap"
        cheap.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
                cost_per_request=0.001,
                data_completeness=0.8,
            )
        ]

        registry.register(expensive)
        registry.register(cheap)

        # With cost constraint, should choose cheap
        constraints = SearchConstraints(
            max_cost_per_request=0.005,
            optimize_for="cost",
        )

        best = registry.get_best_provider(
            OperationType.SEARCH, DataDomain.WEB, constraints=constraints
        )
        assert best.name == "cheap"

        # Without constraint, returns first (expensive)
        best = registry.get_best_provider(OperationType.SEARCH, DataDomain.WEB)
        assert best.name == "expensive"

    def test_get_best_provider_quality_constraint(self, registry):
        """Test provider selection with quality constraints."""
        low_quality = Mock()
        low_quality.name = "low_quality"
        low_quality.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
                cost_per_request=0.001,
                data_completeness=0.6,
            )
        ]

        high_quality = Mock()
        high_quality.name = "high_quality"
        high_quality.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
                cost_per_request=0.01,
                data_completeness=0.95,
            )
        ]

        registry.register(low_quality)
        registry.register(high_quality)

        # With quality constraint, should choose high quality
        constraints = SearchConstraints(
            min_completeness=0.9,
            optimize_for="quality",
        )

        best = registry.get_best_provider(
            OperationType.SEARCH, DataDomain.WEB, constraints=constraints
        )
        assert best.name == "high_quality"

    def test_get_best_provider_feature_requirements(self, registry):
        """Test provider selection with required features."""
        basic = Mock()
        basic.name = "basic"
        basic.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.SOCIAL_MEDIA,
                platform=Platform.TWITTER,
                unique_features=["search"],
            )
        ]

        advanced = Mock()
        advanced.name = "advanced"
        advanced.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.SOCIAL_MEDIA,
                platform=Platform.TWITTER,
                unique_features=["search", "threads", "quoted_tweets"],
            )
        ]

        registry.register(basic)
        registry.register(advanced)

        # Require threads feature
        constraints = SearchConstraints(
            required_features=["threads"],
        )

        best = registry.get_best_provider(
            OperationType.SEARCH,
            DataDomain.SOCIAL_MEDIA,
            Platform.TWITTER,
            constraints=constraints,
        )
        assert best.name == "advanced"

    def test_get_best_provider_optimization_modes(self, registry):
        """Test different optimization modes for provider selection."""
        provider = Mock()
        provider.name = "test"
        provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
                cost_per_request=0.005,
                data_completeness=0.85,
                rate_limit=50,
            )
        ]

        registry.register(provider)

        # Test each optimization mode
        modes: tuple[Literal["cost", "quality", "speed", "balanced"], ...] = (
            "cost",
            "quality",
            "speed",
            "balanced",
        )
        for mode in modes:
            constraints = SearchConstraints(optimize_for=mode)
            best = registry.get_best_provider(
                OperationType.SEARCH, DataDomain.WEB, constraints=constraints
            )
            assert best is not None
            assert best.name == "test"

    def test_capability_index_updates(self, registry):
        """Test that capability index is properly maintained."""
        provider = Mock()
        provider.name = "multi_cap"
        provider.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=Platform.GOOGLE,
            ),
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.NEWS,
                platform=Platform.GOOGLE,
            ),
            ProviderCapability(
                operation=OperationType.ANALYZE,
                domain=DataDomain.SOCIAL_MEDIA,
                platform=None,
            ),
        ]

        registry.register(provider)

        # Check all capabilities are indexed
        web_providers = registry.find_capable_providers(
            OperationType.SEARCH, DataDomain.WEB, Platform.GOOGLE
        )
        assert len(web_providers) == 1

        news_providers = registry.find_capable_providers(
            OperationType.SEARCH, DataDomain.NEWS, Platform.GOOGLE
        )
        assert len(news_providers) == 1

        analyze_providers = registry.find_capable_providers(
            OperationType.ANALYZE, DataDomain.SOCIAL_MEDIA
        )
        assert len(analyze_providers) == 1

        # Unregister and verify index is cleaned
        registry.unregister("multi_cap")

        web_providers = registry.find_capable_providers(
            OperationType.SEARCH, DataDomain.WEB, Platform.GOOGLE
        )
        assert len(web_providers) == 0

    @pytest.mark.asyncio
    async def test_discover_providers(self, registry, monkeypatch):
        """Test auto-discovery of providers via entry points."""
        # Mock entry points
        mock_entry_point = Mock()
        mock_entry_point.name = "test_provider"

        # Create a mock provider class
        mock_provider_class = Mock()
        mock_provider_instance = Mock()
        mock_provider_instance.name = "discovered"
        mock_provider_instance.capabilities = []
        mock_provider_instance.validate = AsyncMock(return_value=True)

        # Mock the create method
        mock_provider_class.create = AsyncMock(return_value=mock_provider_instance)
        mock_entry_point.load.return_value = mock_provider_class

        # Mock importlib.metadata.entry_points
        import importlib.metadata

        mock_entry_points = Mock(return_value=[mock_entry_point])
        monkeypatch.setattr(importlib.metadata, "entry_points", mock_entry_points)

        # Discover providers
        discovered = await registry.discover_providers()

        assert len(discovered) == 1
        assert discovered[0].name == "discovered"
        assert "discovered" in registry.list_providers()

    def test_empty_registry(self, registry):
        """Test behavior with empty registry."""
        # No providers registered
        assert registry.list_providers() == []
        assert registry.get_provider("nonexistent") is None

        providers = registry.find_capable_providers(OperationType.SEARCH, DataDomain.WEB)
        assert providers == []

        best = registry.get_best_provider(OperationType.SEARCH, DataDomain.WEB)
        assert best is None
