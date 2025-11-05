#!/usr/bin/env python3

import asyncio

from good_agent import Agent, AssistantMessage
from good_agent.content import RenderMode
from good_agent.extensions import CitationManager


async def test_citation_fix():
    """Verify the citation mapping bug is fixed."""

    print("=" * 80)
    print("CITATION FIX VERIFICATION TEST")
    print("=" * 80)
    print()

    agent = Agent("Test", extensions=[CitationManager()])
    await agent.ready()
    cm = agent[CitationManager]

    # Setup: Add specific URLs at specific indices
    test_urls = {
        1: "https://first.com",
        2: "https://second.com",
        3: "https://third.com",
        4: "https://fourth.com",
        5: "https://fifth.com",
        6: "https://sixth.com",
    }

    # Add URLs in a specific order to create the index
    for idx in sorted(test_urls.keys()):
        actual_idx = cm.index.add(test_urls[idx])
        assert actual_idx == idx, f"Expected index {idx}, got {actual_idx}"

    print("Global index setup:")
    for idx, url in cm.index.items():
        print(f"  [{idx}]: {url}")
    print()

    # Test: Create message with specific citation references
    test_message = AssistantMessage("""Testing citation resolution:
    - Citation 1: [!CITE_1!] should be first.com
    - Citation 4: [!CITE_4!] should be fourth.com  
    - Citation 6: [!CITE_6!] should be sixth.com
    - Citation 2: [!CITE_2!] should be second.com
    """)

    agent.append(test_message)
    msg = agent[-1]

    print("Test message content:")
    print(msg.content_parts[0].text)
    print()

    # Verify display rendering uses correct URLs from global index
    display_content = msg.render(RenderMode.DISPLAY)

    print("Display rendering:")
    print(display_content)
    print()

    # Verify each citation maps correctly
    tests = [
        (
            "[first.com](https://first.com/)" in display_content,
            "[!CITE_1!] -> first.com",
        ),
        (
            "[fourth.com](https://fourth.com/)" in display_content,
            "[!CITE_4!] -> fourth.com",
        ),
        (
            "[sixth.com](https://sixth.com/)" in display_content,
            "[!CITE_6!] -> sixth.com",
        ),
        (
            "[second.com](https://second.com/)" in display_content,
            "[!CITE_2!] -> second.com",
        ),
    ]

    print("Verification results:")
    all_passed = True
    for passed, description in tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {description}")
        all_passed = all_passed and passed
    print()

    if all_passed:
        print("🎉 SUCCESS: All citations map correctly to global index!")
    else:
        print("❌ FAILURE: Some citations are not mapping correctly")

    await agent.async_close()
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_citation_fix())
    exit(0 if success else 1)
