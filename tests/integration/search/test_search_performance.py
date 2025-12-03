import asyncio
import random
import time
from datetime import date, datetime
from statistics import median

import pytest

from good_agent import Agent
from good_agent.core.types import URL
from good_agent.extensions.search import (
    AgentSearch,
    BaseSearchProvider,
    DataDomain,
    OperationType,
    ProviderCapability,
    SearchResult,
)


class VariableSpeedProvider(BaseSearchProvider):
    """Provider with configurable response time for performance testing."""

    def __init__(self, name: str, delay: float, result_count: int = 10):
        super().__init__()
        self.name = name
        self.delay = delay
        self.result_count = result_count
        self.call_count = 0
        self.capabilities = [
            ProviderCapability(
                operation=OperationType.SEARCH,
                domain=DataDomain.WEB,
                platform=None,
                rate_limit=100,
            )
        ]

    async def search(self, query, capability):
        """Simulate search with delay."""
        self.call_count += 1
        start = time.time()
        await asyncio.sleep(self.delay)
        elapsed = time.time() - start

        return [
            SearchResult(
                platform=self.name,
                id=f"{self.name}_{i}",
                url=URL(f"https://{self.name}.com/{i}"),
                content=f"Result {i} from {self.name} (took {elapsed:.2f}s)",
                content_type="text",
                created_at=datetime.combine(date.today(), datetime.min.time()),
            )
            for i in range(self.result_count)
        ]


class TestPerformance:
    """Test suite for performance characteristics."""

    @pytest.mark.asyncio
    async def test_parallel_execution_performance(self):
        """Test that parallel execution is faster than sequential."""
        # Create multiple slow providers
        providers = [VariableSpeedProvider(f"provider{i}", delay=0.2) for i in range(5)]

        # Test parallel execution
        search_parallel = AgentSearch(
            auto_discover=False,
            providers=providers,
            parallel_execution=True,
        )

        agent_parallel = Agent("Parallel", extensions=[search_parallel])
        await agent_parallel.initialize()

        start = time.time()
        response = await agent_parallel.invoke("search", query="test")
        parallel_time = time.time() - start

        results = response.response
        assert len(results) == 5
        # Should complete in roughly the time of slowest provider (0.2s)
        assert parallel_time < 0.4  # Allow some overhead

        # Test sequential execution
        search_sequential = AgentSearch(
            auto_discover=False,
            providers=providers,
            parallel_execution=False,
        )

        agent_sequential = Agent("Sequential", extensions=[search_sequential])
        await agent_sequential.initialize()

        start = time.time()
        response = await agent_sequential.invoke("search", query="test")
        sequential_time = time.time() - start

        results = response.response
        assert len(results) == 5
        # Should take roughly sum of all delays (5 * 0.2 = 1.0s)
        assert sequential_time >= 0.9

        # Parallel should be significantly faster
        assert parallel_time < sequential_time / 2

    @pytest.mark.asyncio
    async def test_mixed_speed_providers(self):
        """Test performance with providers of varying speeds."""
        providers = [
            VariableSpeedProvider("fast", delay=0.05, result_count=5),
            VariableSpeedProvider("medium", delay=0.2, result_count=10),
            VariableSpeedProvider("slow", delay=0.5, result_count=20),
            VariableSpeedProvider("very_fast", delay=0.01, result_count=3),
        ]

        search = AgentSearch(
            auto_discover=False,
            providers=providers,
            parallel_execution=True,
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        start = time.time()
        response = await agent.invoke("search", query="test")
        total_time = time.time() - start

        results = response.response

        # Should complete in roughly the time of slowest provider
        assert total_time < 0.7  # Slowest is 0.5s + overhead

        # All providers should return results
        assert len(results) == 4
        assert len(results["fast"]) == 5
        assert len(results["medium"]) == 10
        assert len(results["slow"]) == 20
        assert len(results["very_fast"]) == 3

    @pytest.mark.asyncio
    async def test_deduplication_performance(self):
        """Test performance impact of deduplication."""

        async def _invoke_and_measure(agent: Agent, *, query: str) -> float:
            start = time.perf_counter()
            await agent.invoke("search", query=query)
            return time.perf_counter() - start

        # Create providers that return many duplicate results
        class DuplicateProvider(BaseSearchProvider):
            def __init__(self, name: str):
                super().__init__()
                self.name = name
                self.capabilities = [
                    ProviderCapability(
                        operation=OperationType.SEARCH,
                        domain=DataDomain.WEB,
                        platform=None,
                    )
                ]

            async def search(self, query, capability):
                results = []
                for i in range(100):
                    # Every 5th result is duplicate content
                    content = (
                        f"Duplicate content {i // 5}" if i % 5 == 0 else f"Unique {self.name} {i}"
                    )
                    results.append(
                        SearchResult(
                            platform=self.name,
                            id=f"{self.name}_{i}",
                            url=f"https://{self.name}.com/{i}",
                            content=content,
                            content_type="text",
                        )
                    )
                return results

        providers = [DuplicateProvider(f"dup{i}") for i in range(3)]

        # Test with deduplication enabled
        search_dedup = AgentSearch(
            auto_discover=False,
            providers=providers,
            enable_dedup=True,
        )

        agent_dedup = Agent("Dedup", extensions=[search_dedup])
        await agent_dedup.initialize()

        # Warm-up to eliminate first-run overhead
        await agent_dedup.invoke("search", query="warmup")

        response_dedup = await agent_dedup.invoke("search", query="test")

        results_dedup = response_dedup.response

        # Test without deduplication
        search_no_dedup = AgentSearch(
            auto_discover=False,
            providers=providers,
            enable_dedup=False,
        )

        agent_no_dedup = Agent("NoDedup", extensions=[search_no_dedup])
        await agent_no_dedup.initialize()

        # Warm-up to eliminate first-run overhead
        await agent_no_dedup.invoke("search", query="warmup")

        response_no_dedup = await agent_no_dedup.invoke("search", query="test")

        results_no_dedup = response_no_dedup.response

        # Deduplication should remove duplicates
        total_dedup = sum(len(r) for r in results_dedup.values())
        total_no_dedup = sum(len(r) for r in results_no_dedup.values())
        assert total_dedup < total_no_dedup

        # Deduplication shouldn't add significant overhead
        measurement_iterations = 6
        dedup_timings: list[float] = []
        no_dedup_timings: list[float] = []

        for _ in range(measurement_iterations):
            dedup_timings.append(await _invoke_and_measure(agent_dedup, query="benchmark"))
            await asyncio.sleep(0)
            no_dedup_timings.append(await _invoke_and_measure(agent_no_dedup, query="benchmark"))
            await asyncio.sleep(0)

        dedup_median = median(dedup_timings)
        no_dedup_median = median(no_dedup_timings)
        max_multiplier = 1.75
        assert dedup_median < no_dedup_median * max_multiplier, (
            "Deduplication slowdown exceeded threshold: "
            f"median_dedup={dedup_median:.4f}s, median_no_dedup={no_dedup_median:.4f}s, "
            f"allowance={max_multiplier}x, dedup_runs={dedup_timings}, "
            f"no_dedup_runs={no_dedup_timings}"
        )


class TestConcurrency:
    """Test suite for concurrency and thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_searches_different_queries(self):
        """Test multiple concurrent searches with different queries."""

        class QueryTrackingProvider(BaseSearchProvider):
            def __init__(self):
                super().__init__()
                self.name = "tracker"
                self.queries_seen = []
                self.lock = asyncio.Lock()
                self.capabilities = [
                    ProviderCapability(
                        operation=OperationType.SEARCH,
                        domain=DataDomain.WEB,
                        platform=None,
                    )
                ]

            async def search(self, query, capability):
                async with self.lock:
                    self.queries_seen.append(query.text)

                # Simulate some work
                await asyncio.sleep(random.uniform(0.01, 0.05))

                return [
                    SearchResult(
                        platform="tracker",
                        id=f"{query.text}_result",
                        url=f"https://test.com/{query.text}",
                        content=f"Result for: {query.text}",
                        content_type="text",
                    )
                ]

        provider = QueryTrackingProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Launch 20 concurrent searches
        queries = [f"query_{i}" for i in range(20)]
        tasks = [agent.invoke("search", query=q) for q in queries]

        responses = await asyncio.gather(*tasks)
        results = [r.response for r in responses]

        # All queries should have been processed
        assert len(provider.queries_seen) == 20
        assert set(provider.queries_seen) == set(queries)

        # Each result should match its query
        for i, result_set in enumerate(results):
            result = result_set["tracker"][0]
            assert f"query_{i}" in result.content

    @pytest.mark.asyncio
    async def test_concurrent_searches_shared_state(self):
        """Test that concurrent searches don't interfere with each other."""

        class StatefulProvider(BaseSearchProvider):
            def __init__(self):
                super().__init__()
                self.name = "stateful"
                self.search_counter = 0
                self.lock = asyncio.Lock()
                self.capabilities = [
                    ProviderCapability(
                        operation=OperationType.SEARCH,
                        domain=DataDomain.WEB,
                        platform=None,
                    )
                ]

            async def search(self, query, capability):
                # Increment counter safely
                async with self.lock:
                    self.search_counter += 1
                    search_id = self.search_counter

                # Simulate processing
                await asyncio.sleep(0.01)

                return [
                    SearchResult(
                        platform="stateful",
                        id=str(search_id),
                        url=f"https://test.com/{search_id}",
                        content=f"Search #{search_id}: {query.text}",
                        content_type="text",
                    )
                ]

        provider = StatefulProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Launch concurrent searches
        tasks = [agent.invoke("search", query=f"concurrent_{i}") for i in range(50)]

        responses = await asyncio.gather(*tasks)
        results = [r.response for r in responses]

        # Should have made exactly 50 searches
        assert provider.search_counter == 50

        # Each search should have unique ID
        seen_ids = set()
        for result_set in results:
            for result in result_set["stateful"]:
                assert result.id not in seen_ids
                seen_ids.add(result.id)

        assert len(seen_ids) == 50

    @pytest.mark.asyncio
    async def test_provider_rate_limiting(self):
        """Test behavior under rate limiting constraints."""

        class RateLimitedProvider(BaseSearchProvider):
            def __init__(self):
                super().__init__()
                self.name = "rate_limited"
                self.request_times = []
                self.lock = asyncio.Lock()
                self.capabilities = [
                    ProviderCapability(
                        operation=OperationType.SEARCH,
                        domain=DataDomain.WEB,
                        platform=None,
                        rate_limit=10,  # 10 requests per minute
                    )
                ]

            async def search(self, query, capability):
                async with self.lock:
                    now = time.time()
                    self.request_times.append(now)

                    # Check rate limit (simplified - just count recent requests)
                    recent = [t for t in self.request_times if now - t < 60]
                    if len(recent) > 10:
                        raise Exception("Rate limit exceeded")

                return [
                    SearchResult(
                        platform="rate_limited",
                        id="1",
                        url="https://test.com",
                        content="Rate limited result",
                        content_type="text",
                    )
                ]

        provider = RateLimitedProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Try to make more requests than rate limit allows
        results = []
        successful_results = 0
        empty_results = 0

        for i in range(15):
            response = await agent.invoke("search", query=f"test_{i}")
            results.append(response.response)

            # Check if we got actual results or empty due to rate limiting
            if response.response.get("rate_limited"):
                successful_results += 1
            else:
                empty_results += 1

            # Small delay between requests
            await asyncio.sleep(0.01)

        # All requests should return something (even if empty)
        assert len(results) == 15
        # First 10 should succeed (up to rate limit)
        assert successful_results <= 10
        # Remaining should be rate limited (empty results)
        assert empty_results >= 5

    @pytest.mark.asyncio
    async def test_search_cancellation(self):
        """Test that searches can be cancelled."""

        class SlowProvider(BaseSearchProvider):
            def __init__(self):
                super().__init__()
                self.name = "slow"
                self.was_cancelled = False
                self.capabilities = [
                    ProviderCapability(
                        operation=OperationType.SEARCH,
                        domain=DataDomain.WEB,
                        platform=None,
                    )
                ]

            async def search(self, query, capability):
                try:
                    # Long running search
                    await asyncio.sleep(10)
                    return []
                except asyncio.CancelledError:
                    self.was_cancelled = True
                    raise

        provider = SlowProvider()
        search = AgentSearch(
            auto_discover=False,
            providers=[provider],
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        # Start search and cancel it
        task = asyncio.create_task(agent.invoke("search", query="test"))

        # Let it start
        await asyncio.sleep(0.1)

        # Cancel the search
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Provider should have detected cancellation
        assert provider.was_cancelled


class TestScalability:
    """Test suite for scalability and large-scale operations."""

    @pytest.mark.asyncio
    async def test_many_providers(self):
        """Test with many providers registered."""
        # Create 50 providers
        providers = [
            VariableSpeedProvider(f"provider_{i}", delay=0.01, result_count=5) for i in range(50)
        ]

        search = AgentSearch(
            auto_discover=False,
            providers=providers,
            parallel_execution=True,
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        start = time.time()
        response = await agent.invoke("search", query="test")
        elapsed = time.time() - start

        results = response.response
        # Should handle many providers efficiently
        assert len(results) == 50
        # With parallel execution, should be fast even with many providers
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_large_result_aggregation(self):
        """Test aggregating large numbers of results."""

        class LargeResultProvider(BaseSearchProvider):
            def __init__(self, name: str, count: int):
                super().__init__()
                self.name = name
                self.count = count
                self.capabilities = [
                    ProviderCapability(
                        operation=OperationType.SEARCH,
                        domain=DataDomain.WEB,
                        platform=None,
                    )
                ]

            async def search(self, query, capability):
                return [
                    SearchResult(
                        platform=self.name,
                        id=f"{self.name}_{i}",
                        url=f"https://{self.name}.com/{i}",
                        content=f"Result {i}",
                        content_type="text",
                    )
                    for i in range(self.count)
                ]

        providers = [
            LargeResultProvider("small", 10),
            LargeResultProvider("medium", 100),
            LargeResultProvider("large", 1000),
            LargeResultProvider("huge", 5000),
        ]

        search = AgentSearch(
            auto_discover=False,
            providers=providers,
            enable_dedup=False,  # Don't dedup for this test
        )

        agent = Agent("Test", extensions=[search])
        await agent.initialize()

        start = time.time()
        response = await agent.invoke("search", query="test")
        elapsed = time.time() - start

        results = response.response
        # Should handle large result sets
        assert len(results["small"]) == 10
        assert len(results["medium"]) == 100
        assert len(results["large"]) == 1000
        assert len(results["huge"]) == 5000

        total_results = sum(len(r) for r in results.values())
        assert total_results == 6110

        # Should still be reasonably fast
        assert elapsed < 5.0
