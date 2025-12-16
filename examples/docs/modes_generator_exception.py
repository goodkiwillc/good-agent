"""Generator mode handler exception handling.

Demonstrates:
- Catching exceptions from the active phase
- Logging or transforming exceptions
- Suppressing exceptions by not re-raising
- Guaranteed cleanup via try/finally
"""

import asyncio

from good_agent import Agent


async def notify_admin(message: str):
    """Simulate sending admin notification."""
    print(f"  [ADMIN NOTIFICATION] {message}")


async def cleanup_resources():
    """Simulate resource cleanup."""
    print("  [cleanup] Resources cleaned up")


async def main():
    async with Agent("You are a careful assistant.") as agent:

        @agent.modes("careful_mode")
        async def careful_mode(agent: Agent):
            """Mode that catches and logs exceptions."""
            agent.prompt.append("Careful mode - monitoring for errors.")
            print("  [careful] Setup complete")

            try:
                yield agent
            except Exception as e:
                # Log or transform the exception
                agent.mode.state["error"] = str(e)
                await notify_admin(f"Error in careful mode: {e}")
                raise  # Re-raise to propagate
            finally:
                # Always runs, even if exception occurs
                await cleanup_resources()

        @agent.modes("resilient_mode")
        async def resilient_mode(agent: Agent):
            """Mode that suppresses specific exceptions."""
            agent.prompt.append("Resilient mode - recovers from errors.")
            print("  [resilient] Setup complete")

            try:
                yield agent
            except ValueError as e:
                # Suppress ValueError - don't re-raise
                agent.mode.state["recovered"] = True
                agent.mode.state["suppressed_error"] = str(e)
                print(f"  [resilient] Suppressed ValueError: {e}")
            # Other exceptions propagate normally

        print("=== Generator Mode: Exception Handling ===\n")

        # Track results outside mode scope
        careful_error = None
        resilient_recovered = False
        resilient_error = None

        @agent.modes("careful_mode_v2")
        async def careful_mode_v2(agent: Agent):
            """Mode that catches and logs exceptions, exports error."""
            nonlocal careful_error
            agent.prompt.append("Careful mode - monitoring for errors.")
            print("  [careful] Setup complete")

            try:
                yield agent
            except Exception as e:
                careful_error = str(e)
                await notify_admin(f"Error in careful mode: {e}")
                raise
            finally:
                await cleanup_resources()

        @agent.modes("resilient_mode_v2")
        async def resilient_mode_v2(agent: Agent):
            """Mode that suppresses specific exceptions, exports state."""
            nonlocal resilient_recovered, resilient_error
            agent.prompt.append("Resilient mode - recovers from errors.")
            print("  [resilient] Setup complete")

            try:
                yield agent
            except ValueError as e:
                resilient_recovered = True
                resilient_error = str(e)
                print(f"  [resilient] Suppressed ValueError: {e}")

        # Test 1: Exception caught, logged, and re-raised
        print("Test 1: careful_mode catches, logs, and re-raises")
        try:
            async with agent.mode("careful_mode_v2"):
                print("  Raising ValueError inside mode...")
                raise ValueError("Something went wrong")
        except ValueError:
            print("  Exception propagated as expected")
            print(f"  Error recorded: {careful_error}\n")

        # Test 2: Exception suppressed
        print("Test 2: resilient_mode suppresses ValueError")
        async with agent.mode("resilient_mode_v2"):
            print("  Raising ValueError inside mode...")
            raise ValueError("This will be suppressed")
        # If we get here, exception was suppressed
        print("  Exception was suppressed!")
        print(f"  Recovered: {resilient_recovered}")
        print(f"  Suppressed error: {resilient_error}")


if __name__ == "__main__":
    asyncio.run(main())
