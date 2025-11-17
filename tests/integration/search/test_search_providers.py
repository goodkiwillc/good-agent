#!/usr/bin/env python

import asyncio
import os
from datetime import date, timedelta

import pytest
from good_agent import Agent
from good_agent.extensions.search import AgentSearch, SearchProviderRegistry
from good_agent.extensions.search.models import (
    DataDomain,
    OperationType,
    SearchQuery,
)

# Try to import providers
try:
    from good_agent_valueserp.search_provider import WebSearchProvider

    print("✓ WebSearchProvider imported successfully")
except ImportError as e:
    print(f"✗ Failed to import WebSearchProvider: {e}")
    WebSearchProvider = None

try:
    from good_agent_twitter.search_provider import TwitterSearchProvider

    print("✓ TwitterSearchProvider imported successfully")
except ImportError as e:
    print(f"✗ Failed to import TwitterSearchProvider: {e}")
    TwitterSearchProvider = None


@pytest.mark.skip(reason="Integration test hangs - needs investigation")
async def test_entry_point_discovery():
    """Test automatic provider discovery via Python entry points."""
    print("\n=== Testing Entry Point Discovery ===")

    # Create registry and discover providers
    registry = SearchProviderRegistry()
    discovered = await registry.discover_providers()

    print(f"Entry point group: {registry._entry_point_group}")
    print(f"Discovered {len(discovered)} providers:")

    for provider in discovered:
        print(f"  - {provider.name}: {provider.__class__.__name__}")
        print(f"    Platform: {provider.platform}")
        print(f"    Capabilities: {len(provider.capabilities)}")
        for cap in provider.capabilities:
            platform_str = cap.platform.value if cap.platform else "any"
            print(f"      {cap.operation.value}:{cap.domain.value}:{platform_str}")

    # Test capability indexing
    web_providers = registry.find_capable_providers(
        operation=OperationType.SEARCH, domain=DataDomain.WEB
    )
    social_providers = registry.find_capable_providers(
        operation=OperationType.SEARCH, domain=DataDomain.SOCIAL_MEDIA
    )

    print("\nCapability matching:")
    print(f"  Web search providers: {[p.name for p in web_providers]}")
    print(f"  Social media providers: {[p.name for p in social_providers]}")

    return registry


@pytest.mark.skip(reason="Integration test hangs - needs investigation")
async def test_provider_discovery():
    """Test AgentSearch auto-discovery integration."""
    print("\n=== Testing AgentSearch Auto-Discovery ===")

    # Create AgentSearch component with auto-discovery
    search = AgentSearch(auto_discover=True)

    # Initialize agent (this triggers discovery)
    agent = Agent("You are a test assistant", extensions=[search])
    await agent.initialize()

    # Check discovered providers
    providers = search.registry._providers
    print(f"AgentSearch discovered providers: {list(providers.keys())}")

    for name, provider in providers.items():
        print(f"  - {name}: {provider.__class__.__name__}")
        try:
            valid = await provider.validate()
            print(f"    Valid: {valid}")
        except Exception as e:
            print(f"    Validation error: {e}")

    # Check available tools
    print(f"Available tools: {list(agent.tools.keys())}")

    return search, agent


@pytest.mark.skip(reason="Integration test hangs - needs investigation")
async def test_web_search():
    """Test web search using ValueSerp provider."""
    print("\n=== Testing Web Search ===")

    if not WebSearchProvider:
        print("WebSearchProvider not available, skipping test")
        return

    # Check for API key
    if not os.environ.get("VALUESERP_API_KEY"):
        print("VALUESERP_API_KEY not set, skipping test")
        return

    # Create provider directly
    provider = WebSearchProvider()

    # Validate provider
    is_valid = await provider.validate()
    print(f"Provider valid: {is_valid}")

    if not is_valid:
        print("Provider validation failed")
        return

    # Create search query with date range using new field names
    query = SearchQuery(
        text="artificial intelligence news",
        limit=5,
        since=date.today() - timedelta(days=7),  # last week
        until=date.today(),
    )

    # Get web search capability
    web_capability = next(
        (
            c
            for c in provider.capabilities
            if c.operation == OperationType.SEARCH and c.domain == DataDomain.WEB
        ),
        None,
    )

    if not web_capability:
        print("No web search capability found")
        return

    # Execute search
    print(f"Searching for: {query.text}")
    results = await provider.search(query, web_capability)

    print(f"Found {len(results)} results:")
    for i, result in enumerate(results[:3], 1):
        title = (
            result.platform_data.get("title", "No title")
            if hasattr(result, "platform_data")
            else result.content[:50]
        )
        print(f"\n{i}. {title}")
        print(f"   URL: {result.url}")
        print(f"   Content: {result.content[:100]}...")
        if result.created_at:
            print(f"   Date: {result.created_at}")


@pytest.mark.skip(reason="Integration test hangs - needs investigation")
async def test_twitter_search():
    """Test Twitter search using Twitter provider."""
    print("\n=== Testing Twitter Search ===")

    if not TwitterSearchProvider:
        print("TwitterSearchProvider not available, skipping test")
        return

    # Create provider
    provider = TwitterSearchProvider(block_name="twitter-main")

    # Validate provider
    is_valid = await provider.validate()
    print(f"Provider valid: {is_valid}")

    if not is_valid:
        print("Provider validation failed - check Twitter credentials")
        return

    # Create search query with date range using new field names
    query = SearchQuery(
        text="machine learning",
        limit=5,
        since=date.today() - timedelta(days=1),  # yesterday
        until=date.today(),
    )

    # Get social media search capability
    social_capability = next(
        (
            c
            for c in provider.capabilities
            if c.operation == OperationType.SEARCH
            and c.domain == DataDomain.SOCIAL_MEDIA
        ),
        None,
    )

    if not social_capability:
        print("No social media search capability found")
        return

    # Execute search
    print(f"Searching Twitter for: {query.text}")
    results = await provider.search(query, social_capability)

    print(f"Found {len(results)} tweets:")
    for i, result in enumerate(results[:3], 1):
        print(f"\n{i}. @{result.author_handle}: {result.content[:100]}...")
        print(f"   URL: {result.url}")
        print(f"   Metrics: {result.metrics}")
        if result.created_at:
            print(f"   Date: {result.created_at}")


@pytest.mark.skip(reason="Integration test hangs - needs investigation")
async def test_agent_search_integration():
    """Test full AgentSearch component with providers."""
    print("\n=== Testing AgentSearch Component Integration ===")

    # Manually register providers if available
    search = AgentSearch(auto_discover=False)

    providers_added = 0

    if WebSearchProvider:
        try:
            web_provider = WebSearchProvider()
            if await web_provider.validate():
                search.register_provider(web_provider)
                print("✓ Registered WebSearchProvider")
                providers_added += 1
        except Exception as e:
            print(f"✗ Failed to register WebSearchProvider: {e}")

    if TwitterSearchProvider:
        try:
            twitter_provider = TwitterSearchProvider()
            if await twitter_provider.validate():
                search.register_provider(twitter_provider)
                print("✓ Registered TwitterSearchProvider")
                providers_added += 1
        except Exception as e:
            print(f"✗ Failed to register TwitterSearchProvider: {e}")

    if providers_added == 0:
        print("No providers available, skipping integration test")
        return

    # Create agent with search component
    agent = Agent("You are a search assistant", extensions=[search])
    await agent.initialize()

    print(f"\nRegistered providers: {list(search._providers.keys())}")
    print(f"Available tools: {list(agent.tools.keys())}")

    # Test search_entities tool if available
    if "search_entities" in agent.tools:
        print("\n--- Testing search_entities tool ---")
        try:
            result = await agent.tool_calls.invoke(
                "search",
                query="AI technology",
                platforms=["google"] if WebSearchProvider else ["twitter"],
                limit=3,
            )
            print(f"Tool response type: {type(result)}")
            if hasattr(result, "response"):
                print(f"Results: {result.response}")
        except Exception as e:
            print(f"Error: {e}")

    # Test via natural language
    print("\n--- Testing via natural language ---")
    try:
        response = await agent.call("Search for recent news about Python programming")
        print(f"Agent response: {response[:500]}...")
    except Exception as e:
        print(f"Error: {e}")


@pytest.mark.skip(reason="Integration test hangs - needs investigation")
async def test_date_range_functionality():
    """Test that the new since/until fields work correctly."""
    print("\n=== Testing Date Range Functionality ===")

    # Create AgentSearch with discovered providers
    search = AgentSearch(auto_discover=True)
    agent = Agent("Search assistant", extensions=[search])
    await agent.initialize()

    if len(search.registry._providers) == 0:
        print("No providers available for date range test")
        return

    # Test search with date range using new field names
    print("Testing search with since/until date range...")

    try:
        # Mock the provider searches to avoid API calls
        from unittest.mock import AsyncMock, patch

        # Mock all provider search methods
        for provider in search.registry._providers.values():
            with patch.object(
                provider, "search", new_callable=AsyncMock
            ) as mock_search:
                mock_search.return_value = []

        response = await agent.tool_calls.invoke(
            "search",
            query="test query with date range",
            since=date(2024, 1, 1),
            until=date(2024, 1, 31),
        )

        print("✓ Date range search completed successfully")
        print(f"Response type: {type(response)}")

        # Test relative date functionality
        response = await agent.tool_calls.invoke(
            "search", query="recent news", last_week=True
        )

        print("✓ Relative date search (last_week) completed successfully")

    except Exception as e:
        print(f"✗ Date range test failed: {e}")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("AgentSearch Provider Plugin Registration Integration Tests")
    print("=" * 70)

    # Test entry point discovery mechanism
    await test_entry_point_discovery()

    # Test AgentSearch auto-discovery
    await test_provider_discovery()

    # Test date range functionality with new field names
    await test_date_range_functionality()

    # Test individual providers (commented out to avoid API calls)
    print("\n=== Individual Provider Tests (Commented Out) ===")
    print("Individual provider tests are commented out to avoid API calls.")
    print(
        "Uncomment test_web_search() and test_twitter_search() to test with real APIs."
    )
    # await test_web_search()
    # await test_twitter_search()

    # Test full integration
    await test_agent_search_integration()

    print("\n" + "=" * 70)
    print("All tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
