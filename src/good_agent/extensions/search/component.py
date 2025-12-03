import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from good_common.utilities import now_pt

from good_agent.core.components import AgentComponent
from good_agent.extensions.search.models import (
    DataDomain,
    OperationType,
    Platform,
    SearchConstraints,
    SearchQuery,
    SearchResult,
    UserResult,
)
from good_agent.extensions.search.providers import (
    SearchProvider,
    SearchProviderRegistry,
)
from good_agent.tools import tool

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AgentSearch(AgentComponent):
    """Discovery component that routes search queries across registered providers."""

    def __init__(
        self,
        auto_discover: bool = True,
        providers: list[SearchProvider] | None = None,
        default_limit: int = 10,
        enable_dedup: bool = True,
        parallel_execution: bool = True,
        **kwargs,
    ):
        """
        Initialize AgentSearch component.

        Args:
            auto_discover: Auto-discover providers via entry points
            providers: Manual list of providers to register
            default_limit: Default result limit per search
            enable_dedup: Enable cross-platform deduplication
            parallel_execution: Execute multi-platform searches in parallel
        """
        super().__init__(**kwargs)
        logger.warning("AgentSearch component is experimental and may change in future releases.")

        self.registry = SearchProviderRegistry()
        self.auto_discover = auto_discover
        self.default_limit = default_limit
        self.enable_dedup = enable_dedup
        self.parallel_execution = parallel_execution

        # Register provided providers
        if providers:
            for provider in providers:
                self.registry.register(provider)

    async def install(self, agent):
        """Install component and discover providers."""
        await super().install(agent)

        if self.auto_discover:
            # Auto-discover providers
            discovered = await self.registry.discover_providers()
            logger.info(f"AgentSearch discovered {len(discovered)} providers")

    # ============= Core Search Tools =============

    @tool
    async def search(
        self,
        query: str,
        platforms: list[str] | None = None,
        domains: list[str] | None = None,
        limit: int | None = None,
        content_type: Literal["all", "text", "image", "video"] = "all",
        since: date | None = None,
        until: date | None = None,
        timeframe: Literal["last_day", "last_week", "last_month"] | None = None,
        sort_by: Literal["relevance", "recent", "popular"] = "relevance",
        # Provider constraint parameters
        max_cost: float | None = None,
        min_quality: float | None = None,
        required_features: list[str] | None = None,
        optimize_for: Literal["cost", "quality", "speed", "balanced", "all"] = "all",
    ) -> dict[str, list[SearchResult]]:
        """Query registered providers with optional domain/platform/constraint filters."""
        limit = limit or self.default_limit

        # Calculate date range based on relative time windows
        today = self.agent.vars.get("today", now_pt().date())

        # Relative time windows override explicit dates
        if timeframe == "last_day":
            since = today - timedelta(days=1)
            until = today
        elif timeframe == "last_week":
            since = today - timedelta(days=7)
            until = today
        elif timeframe == "last_month":
            since = today - timedelta(days=30)
            until = today

        # Convert dates to datetime for query
        date_from_dt = datetime.combine(since, datetime.min.time()) if since else None
        date_to_dt = datetime.combine(until, datetime.max.time()) if until else None

        # Build unified query
        unified_query = SearchQuery(
            text=query,
            content_type=content_type,
            since=date_from_dt,
            until=date_to_dt,
            limit=limit,
            sort_by=sort_by,
        )

        # Determine which providers to use
        if optimize_for == "all":
            # Use all capable providers (original behavior)
            providers = self._select_providers(platforms, domains)
        else:
            # Use constraint-based selection for optimized provider choice
            constraints = SearchConstraints(
                max_cost_per_request=max_cost,
                min_completeness=min_quality,
                required_features=required_features or [],
                optimize_for=optimize_for if optimize_for != "all" else "balanced",
            )
            providers = self._select_providers_with_constraints(platforms, domains, constraints)

        if not providers:
            logger.warning(f"No providers available for platforms={platforms}, domains={domains}")
            return {}

        logger.info(f"Search starting with {len(providers)} providers")

        try:
            # Execute searches
            if self.parallel_execution and len(providers) > 1:
                logger.info("Using parallel search")
                results = await self._parallel_search(unified_query, providers)
            else:
                results = await self._sequential_search(unified_query, providers)

            # Post-process results
            if self.enable_dedup:
                results = self._deduplicate_results(results)

            # Note: Citation tracking happens automatically via tool execution hooks
            # Other components can listen to tool events to track citations

            # Avoid logging full result payloads to keep search fast
            try:
                summary = {k: len(v) for k, v in results.items()}
                logger.info(f"Search returning results (counts): {summary}")
            except Exception:
                logger.info("Search returning results (counts unavailable)")
            return results
        except Exception as e:
            logger.error(f"Search failed with exception: {e}")
            # Return empty results instead of raising
            return {}

    @tool
    async def search_entities(
        self,
        entity_type: Literal["person", "company", "organization"],
        name: str | None = None,
        filters: dict[str, Any] | None = None,
        provider_names: list[str] | None = None,
        limit: int | None = None,
    ) -> list[UserResult]:
        """
        Search for entity profiles (people, companies, organizations).

        Specialized search for finding profiles across professional
        and social platforms.

        Args:
            entity_type: Type of entity to search for
            name: Name to search for
            filters: Additional filters (e.g., {"title": "CEO", "location": "NYC"})
            provider_names: Specific provider names to use (optional)
            limit: Maximum results

        Returns:
            List of entity/profile results

        Examples:
            Find person: search_entities("person", name="John Smith")
            Find company: search_entities("company", name="OpenAI")
            Filtered search: search_entities("person", filters={"title": "CTO", "company": "Google"})
        """
        limit = limit or self.default_limit
        filters = filters or {}

        # Build entity search query
        query_text = name or ""
        if filters:
            # Add filters to query text (provider-specific transformation will handle)
            for key, value in filters.items():
                query_text += f" {key}:{value}"

        query = SearchQuery(text=query_text, limit=limit)

        # Map entity type to domain
        domain_map = {
            "person": DataDomain.PEOPLE,
            "company": DataDomain.COMPANIES,
            "organization": DataDomain.COMPANIES,
        }
        domain = domain_map[entity_type]

        # Find capable providers based on domain and operation
        providers = self.registry.find_capable_providers(OperationType.SEARCH, domain)

        # Filter to specific providers if requested
        if provider_names:
            providers = [p for p in providers if p.name in provider_names]

        if not providers:
            logger.warning(f"No providers for entity search: {entity_type}")
            return []

        # Execute searches and collect results
        all_results = []
        for provider in providers:
            try:
                capability = provider.get_capability(OperationType.SEARCH, domain)
                if capability:
                    results = await provider.search(query, capability)
                    # Convert SearchResult to UserResult for entity searches
                    for result in results:
                        user_result = self._search_result_to_user_result(result)
                        if user_result:
                            all_results.append(user_result)
            except Exception as e:
                logger.error(f"Entity search failed with {provider.name}: {e}")

        return all_results

    @tool
    async def trending_topics(
        self,
        platforms: list[str] | None = None,
        category: str | None = None,
        location: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get trending topics across platforms.

        Discovers what's currently trending on social media and news platforms.

        Args:
            platforms: Platforms to check (e.g., ["twitter", "reddit"])
            category: Category filter (e.g., "technology", "politics")
            location: Geographic location (e.g., "United States", "global")

        Returns:
            Dictionary mapping platforms to trending topics

        Examples:
            Global trends: trending_topics()
            Platform-specific: trending_topics(platforms=["twitter"])
            Category trends: trending_topics(category="technology")
        """
        # Find providers with trend analysis capability
        providers = self.registry.find_capable_providers(
            OperationType.ANALYZE, DataDomain.SOCIAL_MEDIA
        )

        if platforms:
            # Filter to requested platforms
            platform_set = set(platforms)
            providers = [p for p in providers if p.platform and p.platform.value in platform_set]

        if not providers:
            return {"error": [{"message": "No providers support trend analysis"}]}

        trends: dict[str, list[dict[str, Any]]] = {}
        for provider in providers:
            try:
                # Note: This would need a trending-specific method in providers
                # For now, using search with special parameters
                query = SearchQuery(
                    text="",  # Empty query for trends
                    limit=20,
                    sort_by="popular",
                )

                # Add location/category as provider-specific params
                if location:
                    query.location = location

                capability = provider.get_capability(OperationType.ANALYZE, DataDomain.SOCIAL_MEDIA)
                if capability:
                    # This would ideally call a trends-specific method
                    results = await provider.search(query, capability)
                    trends[provider.platform.value if provider.platform else provider.name] = [
                        {"topic": r.content, "metrics": r.metrics} for r in results[:10]
                    ]
            except Exception as e:
                logger.error(f"Failed to get trends from {provider.name}: {e}")

        return trends

    # ============= Helper Methods =============

    def _select_providers(
        self,
        platforms: list[str] | None,
        domains: list[str] | None,
    ) -> list[SearchProvider]:
        """Select providers based on platform/domain requirements."""
        providers = []

        if platforms:
            # Get providers for specific platforms
            for platform_str in platforms:
                try:
                    platform = Platform[platform_str.upper()]
                    # Try to find providers for this platform across all domains
                    for domain in DataDomain:
                        domain_providers = self.registry.find_capable_providers(
                            OperationType.SEARCH,
                            domain,
                            platform,
                        )
                        # When searching by platform, only include providers that
                        # explicitly support this platform (not cross-platform ones)
                        for provider in domain_providers:
                            # Check if provider has a capability with this specific platform
                            for cap in provider.capabilities:
                                if (
                                    cap.operation == OperationType.SEARCH
                                    and cap.domain == domain
                                    and cap.platform == platform
                                ):
                                    providers.append(provider)
                                    break
                except KeyError:
                    logger.warning(f"Unknown platform: {platform_str}")

        if domains:
            # Get providers for specific domains
            for domain_str in domains:
                try:
                    domain = DataDomain[domain_str.upper()]
                    domain_providers = self.registry.find_capable_providers(
                        OperationType.SEARCH, domain
                    )
                    logger.info(
                        f"Found {len(domain_providers)} providers for domain {domain}: {[p.name for p in domain_providers]}"
                    )
                    providers.extend(domain_providers)
                except KeyError:
                    logger.warning(f"Unknown domain: {domain_str}")

        if not platforms and not domains:
            # No specific requirements - get all search providers
            for domain in DataDomain:
                providers.extend(self.registry.find_capable_providers(OperationType.SEARCH, domain))

        # Deduplicate providers
        seen = set()
        unique_providers = []
        for provider in providers:
            if provider.name not in seen:
                seen.add(provider.name)
                unique_providers.append(provider)

        return unique_providers

    def _select_providers_with_constraints(
        self,
        platforms: list[str] | None,
        domains: list[str] | None,
        constraints: SearchConstraints,
    ) -> list[SearchProvider]:
        """Select best providers based on constraints.

        Unlike _select_providers which returns ALL matching providers,
        this returns the BEST provider per domain/platform based on
        the provided constraints.
        """
        providers = []
        processed_combinations = set()

        # If specific platforms requested, find best provider for each
        if platforms:
            for platform_str in platforms:
                try:
                    platform = Platform[platform_str.upper()]
                    # Find best provider for this platform across all domains
                    for domain in DataDomain:
                        combo_key = (domain, platform)
                        if combo_key not in processed_combinations:
                            provider = self.registry.get_best_provider(
                                OperationType.SEARCH,
                                domain,
                                platform,
                                constraints=constraints,
                            )
                            if provider and provider not in providers:
                                providers.append(provider)
                                processed_combinations.add(combo_key)
                except KeyError:
                    logger.warning(f"Unknown platform: {platform_str}")

        # If specific domains requested, find best provider for each
        if domains:
            for domain_str in domains:
                try:
                    domain = DataDomain[domain_str.upper()]
                    # Only process if we haven't already handled this domain
                    if not any((domain, p) in processed_combinations for p in Platform):
                        provider = self.registry.get_best_provider(
                            OperationType.SEARCH, domain, constraints=constraints
                        )
                        if provider and provider not in providers:
                            providers.append(provider)
                except KeyError:
                    logger.warning(f"Unknown domain: {domain_str}")

        # If neither platforms nor domains specified, get best provider for each domain
        if not platforms and not domains:
            for domain in [DataDomain.WEB, DataDomain.SOCIAL_MEDIA, DataDomain.NEWS]:
                provider = self.registry.get_best_provider(
                    OperationType.SEARCH, domain, constraints=constraints
                )
                if provider and provider not in providers:
                    providers.append(provider)

        return providers

    async def _parallel_search(
        self,
        query: SearchQuery,
        providers: list[SearchProvider],
    ) -> dict[str, list[SearchResult]]:
        """Execute searches in parallel across providers."""
        tasks = []
        provider_names = []

        for provider in providers:
            # Get appropriate capability for this provider
            capability = None
            for cap in provider.capabilities:
                if cap.operation == OperationType.SEARCH:
                    capability = cap
                    break

            if capability:
                tasks.append(provider.search(query, capability))
                provider_names.append(provider.name)

        if not tasks:
            return {}

        # Execute in parallel with timeout
        try:
            # Add overall timeout for parallel searches (default 30 seconds)
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=30.0
            )
        except TimeoutError:
            logger.error("Parallel search timed out after 30 seconds")
            # Return empty results for all providers that timed out
            return {name: [] for name in provider_names}
        except Exception as e:
            logger.error(f"Parallel search failed: {e}")
            return {}

        # Build results dictionary
        search_results: dict[str, list[SearchResult]] = {}
        for name, result in zip(provider_names, results, strict=False):
            if isinstance(result, Exception):
                logger.error(f"Search failed for {name}: {result}")
                search_results[name] = []
            elif result is None:
                logger.error(f"Search returned None for {name}")
                search_results[name] = []
            else:
                # Type narrowing: result is list[SearchResult] here
                search_results[name] = result  # type: ignore[assignment]

        return search_results

    async def _sequential_search(
        self,
        query: SearchQuery,
        providers: list[SearchProvider],
    ) -> dict[str, list[SearchResult]]:
        """Execute searches sequentially across providers."""
        results = {}

        for provider in providers:
            try:
                # Get appropriate capability
                capability = None
                for cap in provider.capabilities:
                    if cap.operation == OperationType.SEARCH:
                        capability = cap
                        break

                if capability:
                    provider_results = await provider.search(query, capability)
                    results[provider.name] = provider_results
            except Exception as e:
                logger.error(f"Search failed for {provider.name}: {e}")
                results[provider.name] = []

        return results

    def _deduplicate_results(
        self,
        results: dict[str, list[SearchResult]],
    ) -> dict[str, list[SearchResult]]:
        """Remove duplicate content across platforms."""
        # Use a set of normalized content snippets for O(1) duplicate checks
        # Keep the operation extremely lightweight to avoid performance overhead
        seen: set[str] = set()
        deduped: dict[str, list[SearchResult]] = {}

        for platform, platform_results in results.items():
            bucket: list[SearchResult] = []
            for result in platform_results:
                # Normalize a small prefix for comparison; keep case-insensitive behavior
                content = result.content or ""
                key = content[:200].lower().strip() if content else ""

                # Preserve empty-content results; otherwise dedup by normalized key
                if not key or key not in seen:
                    if key:
                        seen.add(key)
                    bucket.append(result)

            deduped[platform] = bucket

        return deduped

    def _search_result_to_user_result(self, result: SearchResult) -> UserResult | None:
        """Convert a SearchResult to UserResult for entity searches."""
        if not result.author_name:
            return None

        return UserResult(
            platform=result.platform,
            id=result.author_id or result.id,
            username=result.author_handle or result.author_name,
            display_name=result.author_name,
            profile_url=result.author_url or result.url,
            verified=result.author_verified,
            platform_data=result.platform_data,
        )
