import importlib.metadata
import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from good_agent.extensions.search.models import (
    DataDomain,
    OperationType,
    Platform,
    ProviderCapability,
    SearchConstraints,
    SearchQuery,
    SearchResult,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class SearchProvider(Protocol):
    """
    Protocol that all search providers must implement.

    Providers can be registered via:
    1. Python entry points (auto-discovery)
    2. Manual registration
    3. Dynamic loading
    """

    # Provider metadata
    name: str  # Unique provider name
    platform: Platform | None  # Primary platform (None for multi-platform)
    capabilities: list[ProviderCapability]  # List of capabilities

    async def search(
        self,
        query: SearchQuery,
        capability: ProviderCapability,
    ) -> list[SearchResult]:
        """
        Execute a search with the specified capability.

        Args:
            query: Unified search query
            capability: The specific capability to use

        Returns:
            List of search results in standardized format
        """
        ...

    async def validate(self) -> bool:
        """
        Validate that the provider is properly configured and operational.

        Returns:
            True if provider is ready to use
        """
        ...

    def transform_query(self, query: SearchQuery) -> dict[str, Any]:
        """
        Transform unified query to provider-specific format.

        Args:
            query: Unified search query

        Returns:
            Provider-specific query parameters
        """
        ...

    def has_capability(
        self,
        operation: OperationType,
        domain: DataDomain,
        platform: Platform | None = None,
    ) -> bool:
        """
        Check if provider has a specific capability.

        Args:
            operation: The operation type to check
            domain: The data domain to check
            platform: Optional platform to filter by

        Returns:
            True if provider has the capability
        """
        ...

    def get_capability(
        self,
        operation: OperationType,
        domain: DataDomain,
        platform: Platform | None = None,
        method: str | None = None,
    ) -> ProviderCapability | None:
        """
        Get specific capability if it exists.

        Args:
            operation: The operation type to get
            domain: The data domain to get
            platform: Optional platform to filter by
            method: Optional method to filter by

        Returns:
            The matching capability or None
        """
        ...


class BaseSearchProvider(ABC):
    """
    Base class for search providers with common functionality.

    Concrete providers should inherit from this class.
    """

    name: str = ""
    platform: Platform | None = None
    capabilities: list[ProviderCapability] = []

    def __init__(self):
        """Initialize provider with default values."""
        if not self.name:
            self.name = self.__class__.__name__.replace("Provider", "").lower()

    @abstractmethod
    async def search(
        self,
        query: SearchQuery,
        capability: ProviderCapability,
    ) -> list[SearchResult]:
        """Execute search - must be implemented by subclass."""
        pass

    async def validate(self) -> bool:
        """Default validation - override for specific checks."""
        return True

    def transform_query(self, query: SearchQuery) -> dict[str, Any]:
        """Default query transformation - override for specific logic."""
        params: dict[str, Any] = {}

        if query.text:
            params["q"] = query.text
        if query.limit:
            params["limit"] = query.limit
        if query.offset:
            params["offset"] = query.offset

        return params

    def has_capability(
        self,
        operation: OperationType,
        domain: DataDomain,
        platform: Platform | None = None,
    ) -> bool:
        """Check if provider has a specific capability."""
        for cap in self.capabilities:
            if (
                cap.operation == operation
                and cap.domain == domain
                and (platform is None or cap.platform == platform)
            ):
                return True
        return False

    def get_capability(
        self,
        operation: OperationType,
        domain: DataDomain,
        platform: Platform | None = None,
        method: str | None = None,
    ) -> ProviderCapability | None:
        """Get specific capability if it exists."""
        for cap in self.capabilities:
            if (
                cap.operation == operation
                and cap.domain == domain
                and (platform is None or cap.platform == platform)
                and (method is None or cap.method == method)
            ):
                return cap
        return None


class SearchProviderRegistry:
    """
    Registry for discovering and managing search providers.

    Supports:
    - Auto-discovery via entry points
    - Manual registration
    - Capability queries
    - Provider validation
    """

    def __init__(self):
        """Initialize empty registry."""
        self._providers: dict[str, SearchProvider] = {}
        self._entry_point_group = "good_agent.search_providers"
        self._capability_index: dict[
            tuple, list[str]
        ] = {}  # (op, domain, platform) -> [provider_names]

    async def discover_providers(self) -> list[SearchProvider]:
        """
        Auto-discover providers via Python entry points.

        Returns:
            List of discovered and validated providers
        """
        discovered = []

        try:
            # Load entry points
            entry_points = importlib.metadata.entry_points(group=self._entry_point_group)

            for entry_point in entry_points:
                try:
                    # Load provider class
                    provider_class = entry_point.load()

                    # Instantiate provider
                    if hasattr(provider_class, "create"):
                        # Async factory method
                        provider = await provider_class.create()
                    else:
                        # Direct instantiation
                        provider = provider_class()

                    # Validate provider
                    if await provider.validate():
                        self.register(provider)
                        discovered.append(provider)
                        logger.info(f"Discovered search provider: {provider.name}")
                    else:
                        logger.warning(f"Provider {entry_point.name} failed validation")

                except Exception as e:
                    logger.error(f"Failed to load provider {entry_point.name}: {e}")

        except Exception as e:
            logger.error(f"Failed to discover providers: {e}")

        return discovered

    def register(self, provider: SearchProvider) -> None:
        """
        Register a search provider.

        Args:
            provider: Provider instance to register
        """
        self._providers[provider.name] = provider

        # Update capability index
        for capability in provider.capabilities:
            key = (capability.operation, capability.domain, capability.platform)
            if key not in self._capability_index:
                self._capability_index[key] = []
            if provider.name not in self._capability_index[key]:
                self._capability_index[key].append(provider.name)

        logger.debug(
            f"Registered provider {provider.name} with {len(provider.capabilities)} capabilities"
        )

    def unregister(self, provider_name: str) -> None:
        """
        Unregister a provider.

        Args:
            provider_name: Name of provider to remove
        """
        if provider_name in self._providers:
            provider = self._providers[provider_name]

            # Remove from capability index
            for capability in provider.capabilities:
                key = (capability.operation, capability.domain, capability.platform)
                if key in self._capability_index:
                    self._capability_index[key] = [
                        name for name in self._capability_index[key] if name != provider_name
                    ]

            del self._providers[provider_name]
            logger.debug(f"Unregistered provider {provider_name}")

    def get_provider(self, name: str) -> SearchProvider | None:
        """Get provider by name."""
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def find_capable_providers(
        self,
        operation: OperationType,
        domain: DataDomain,
        platform: Platform | None = None,
    ) -> list[SearchProvider]:
        """
        Find all providers with a specific capability.

        Args:
            operation: Operation type needed
            domain: Data domain needed
            platform: Specific platform (optional)

        Returns:
            List of capable providers
        """
        provider_names = []

        if platform is not None:
            # Platform specified - look for exact match and cross-platform
            exact_key = (operation, domain, platform)
            provider_names.extend(self._capability_index.get(exact_key, []))

            # Also include cross-platform providers
            cross_platform_key = (operation, domain, None)
            provider_names.extend(self._capability_index.get(cross_platform_key, []))
        else:
            # No platform specified - find all providers for this operation+domain
            # regardless of platform
            for key, names in self._capability_index.items():
                key_operation, key_domain, key_platform = key
                if key_operation == operation and key_domain == domain:
                    provider_names.extend(names)

        # Return provider instances (deduplicated)
        providers = []
        seen = set()
        for name in provider_names:
            if name not in seen and (provider := self._providers.get(name)):
                providers.append(provider)
                seen.add(name)

        return providers

    def get_best_provider(
        self,
        operation: OperationType,
        domain: DataDomain,
        platform: Platform | None = None,
        constraints: SearchConstraints | None = None,
    ) -> SearchProvider | None:
        """
        Get the best provider for a specific operation.

        Simple scoring based on constraints - can be extended
        with more sophisticated selection logic.

        Args:
            operation: Operation type needed
            domain: Data domain needed
            platform: Specific platform (optional)
            constraints: Requirements and preferences

        Returns:
            Best matching provider or None
        """
        candidates = self.find_capable_providers(operation, domain, platform)

        if not candidates:
            return None

        if not constraints:
            # No constraints - return first available
            return candidates[0]

        # Score each provider
        scored = []
        for provider in candidates:
            score = self._score_provider(provider, operation, domain, platform, constraints)
            if score > 0:  # Only include viable providers
                scored.append((score, provider))

        if not scored:
            return None

        # Return highest scoring provider
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[0][1]

    def _score_provider(
        self,
        provider: SearchProvider,
        operation: OperationType,
        domain: DataDomain,
        platform: Platform | None,
        constraints: SearchConstraints,
    ) -> float:
        """
        Score a provider based on constraints.

        Returns:
            Score from 0-1, or -1 if provider doesn't meet hard constraints
        """
        # Get the specific capability
        capability = None
        for cap in provider.capabilities:
            if (
                cap.operation == operation
                and cap.domain == domain
                and (platform is None or cap.platform == platform)
            ):
                capability = cap
                break

        if not capability:
            return -1

        # Check hard constraints
        if (
            constraints.max_cost_per_request
            and capability.cost_per_request > constraints.max_cost_per_request
        ):
            return -1

        if (
            constraints.min_completeness
            and capability.data_completeness < constraints.min_completeness
        ):
            return -1

        if (
            constraints.min_data_freshness
            and capability.data_freshness > constraints.min_data_freshness
        ):
            return -1

        if constraints.required_features:
            if not all(f in capability.unique_features for f in constraints.required_features):
                return -1

        # Calculate score based on optimization preference
        score = 0.5  # Base score

        if constraints.optimize_for == "cost":
            # Prefer lower cost
            if capability.cost_per_request == 0:
                score += 0.5
            else:
                max_cost = constraints.max_cost_per_request or 1.0
                score += 0.5 * (1 - capability.cost_per_request / max_cost)

        elif constraints.optimize_for == "quality":
            # Prefer higher completeness
            score += 0.5 * capability.data_completeness

        elif constraints.optimize_for == "speed":
            # Prefer higher rate limits (proxy for speed)
            score += 0.5 * min(1.0, capability.rate_limit / 100)

        else:  # balanced
            # Equal weight to cost and quality
            cost_score = 0.5 if capability.cost_per_request == 0 else 0.25
            quality_score = 0.25 * capability.data_completeness
            score += cost_score + quality_score

        return score
