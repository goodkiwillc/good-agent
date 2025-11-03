#!/usr/bin/env python3
"""
Quick test to demonstrate SearchProviderRegistry behavior
"""

import asyncio

from good_agent.extensions.search import SearchProviderRegistry


async def test_registry_behavior():
    print("=== Testing SearchProviderRegistry Behavior ===\n")

    # Step 1: Create empty registry
    print("1. Creating new registry...")
    registry = SearchProviderRegistry()

    print(f"   Providers before discovery: {registry.list_providers()}")
    print(f"   Registry._providers: {dict(registry._providers)}")
    print(f"   Length: {len(registry._providers)}")

    print("\n2. Calling discover_providers()...")
    discovered = await registry.discover_providers()

    print(f"   Discovered providers: {[p.name for p in discovered]}")
    print(f"   Providers after discovery: {registry.list_providers()}")
    print(f"   Registry._providers: {list(registry._providers.keys())}")
    print(f"   Length: {len(registry._providers)}")

    print("\n3. Provider details:")
    for name, provider in registry._providers.items():
        print(f"   - {name}: {provider.__class__.__name__}")
        try:
            valid = await provider.validate()
            print(f"     Valid: {valid}")
        except Exception as e:
            print(f"     Validation error: {e}")

    print("\n=== Registry Methods ===")
    print(f"list_providers(): {registry.list_providers()}")

    # Test get_provider
    if registry.list_providers():
        first_provider_name = registry.list_providers()[0]
        provider = registry.get_provider(first_provider_name)
        print(
            f"get_provider('{first_provider_name}'): {provider.name if provider else None}"
        )


if __name__ == "__main__":
    asyncio.run(test_registry_behavior())
