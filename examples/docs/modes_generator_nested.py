"""Generator pattern: Nested Generators.

Demonstrates:
- Combining multiple generator modes
- Cleanup order (LIFO - inner first, then outer)
- State inheritance between nested modes
- Guaranteed cleanup for all levels
"""

import asyncio

from good_agent import Agent


async def main():
    async with Agent("You are a helpful assistant.") as agent:

        @agent.modes("outer")
        async def outer_mode(agent: Agent):
            """Outer mode with event tracking."""
            events = []
            events.append("outer:setup")
            agent.mode.state["events"] = events
            agent.prompt.append("Outer mode active.")

            print("  [outer] Setup complete")

            try:
                yield agent
            finally:
                events.append("outer:cleanup")
                print("  [outer] Cleanup complete")

        @agent.modes("inner")
        async def inner_mode(agent: Agent):
            """Inner mode that adds to outer's events."""
            # Access events from outer mode's state
            events = agent.mode.state.get("events", [])
            events.append("inner:setup")
            agent.prompt.append("Inner mode active.")

            print("  [inner] Setup complete")

            try:
                yield agent
            finally:
                events.append("inner:cleanup")
                print("  [inner] Cleanup complete")

        print("=== Generator Pattern: Nested Generators ===\n")

        # Track events outside mode scope
        captured_events: list[str] = []

        @agent.modes("outer_tracked")
        async def outer_tracked_mode(agent: Agent):
            """Outer mode that exports events."""
            captured_events.append("outer:setup")
            agent.mode.state["local_events"] = captured_events
            agent.prompt.append("Outer mode active.")
            print("  [outer] Setup complete")

            try:
                yield agent
            finally:
                captured_events.append("outer:cleanup")
                print("  [outer] Cleanup complete")

        @agent.modes("inner_tracked")
        async def inner_tracked_mode(agent: Agent):
            """Inner mode that adds to outer's events."""
            captured_events.append("inner:setup")
            agent.prompt.append("Inner mode active.")
            print("  [inner] Setup complete")

            try:
                yield agent
            finally:
                captured_events.append("inner:cleanup")
                print("  [inner] Cleanup complete")

        # Test 1: Normal nested execution
        print("Test 1: Normal nested execution")
        async with agent.mode("outer_tracked"):
            print(f"  Stack: {agent.mode.stack}")

            async with agent.mode("inner_tracked"):
                print(f"  Stack: {agent.mode.stack}")
                captured_events.append("inner:active")

            print(f"  Stack after inner: {agent.mode.stack}")

        print(f"  Event order: {captured_events}")
        print("  (Note: inner cleanup before outer cleanup)\n")

        # Reset for test 2
        captured_events.clear()

        # Test 2: Exception in inner mode
        print("Test 2: Exception in inner mode (both cleanups run)")
        try:
            async with agent.mode("outer_tracked"), agent.mode("inner_tracked"):
                captured_events.append("inner:active")
                raise ValueError("Error in inner mode")
        except ValueError as e:
            print(f"  Caught: {e}")

        print(f"  Event order: {captured_events}")
        print("  (Both cleanups ran despite exception)")


if __name__ == "__main__":
    asyncio.run(main())
