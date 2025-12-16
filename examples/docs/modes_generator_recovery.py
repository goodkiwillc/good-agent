"""Generator pattern: Error Recovery.

Demonstrates:
- Handling different exception types
- Suppressing recoverable errors
- Logging and re-raising critical errors
- Guaranteed cleanup via finally
"""

import asyncio

from good_agent import Agent


class RateLimitError(Exception):
    """Simulated rate limit error (recoverable)."""

    pass


class CriticalError(Exception):
    """Simulated critical error (not recoverable)."""

    pass


async def log_critical_error(error: Exception):
    """Simulate logging a critical error."""
    print(f"  [CRITICAL LOG] {type(error).__name__}: {error}")


async def log_session_end(errors: list, attempts: int):
    """Simulate logging session end."""
    print(f"  [SESSION LOG] Ended with {len(errors)} errors, {attempts} attempts")


async def main():
    async with Agent("You are a resilient assistant.") as agent:

        @agent.modes("resilient")
        async def resilient_mode(agent: Agent):
            """Resilient mode with error recovery."""
            agent.mode.state["attempts"] = 0
            agent.mode.state["errors"] = []
            agent.prompt.append("Resilient mode active.")

            print("  [resilient] Setup complete")

            try:
                yield agent
            except RateLimitError as e:
                agent.mode.state["errors"].append(str(e))
                # Suppress and let caller retry
                agent.mode.state["should_retry"] = True
                print(f"  [resilient] Rate limit suppressed: {e}")
            except CriticalError as e:
                # Log but re-raise
                await log_critical_error(e)
                raise
            finally:
                # Always log completion
                errors = agent.mode.state.get("errors", [])
                attempts = agent.mode.state.get("attempts", 0)
                await log_session_end(errors, attempts)

        print("=== Generator Pattern: Error Recovery ===\n")

        # Track results outside mode scope
        should_retry = False
        recorded_errors: list[str] = []

        @agent.modes("resilient_tracked")
        async def resilient_tracked_mode(agent: Agent):
            """Resilient mode that exports state."""
            nonlocal should_retry, recorded_errors
            agent.mode.state["attempts"] = 0
            agent.mode.state["errors"] = []
            agent.prompt.append("Resilient mode active.")
            print("  [resilient] Setup complete")

            try:
                yield agent
            except RateLimitError as e:
                agent.mode.state["errors"].append(str(e))
                should_retry = True
                print(f"  [resilient] Rate limit suppressed: {e}")
            except CriticalError as e:
                await log_critical_error(e)
                raise
            finally:
                recorded_errors = list(agent.mode.state["errors"])
                errors = agent.mode.state.get("errors", [])
                attempts = agent.mode.state.get("attempts", 0)
                await log_session_end(errors, attempts)

        # Test 1: RateLimitError (suppressed)
        print("Test 1: RateLimitError (recoverable, suppressed)")
        should_retry = False
        recorded_errors = []
        async with agent.mode("resilient_tracked"):
            agent.mode.state["attempts"] += 1
            raise RateLimitError("Too many requests")
        print(f"  Should retry: {should_retry}")
        print(f"  Errors recorded: {recorded_errors}\n")

        # Test 2: CriticalError (logged and re-raised)
        print("Test 2: CriticalError (logged, re-raised)")
        should_retry = False
        recorded_errors = []
        try:
            async with agent.mode("resilient_tracked"):
                agent.mode.state["attempts"] += 1
                raise CriticalError("Database connection lost")
        except CriticalError as e:
            print(f"  Exception propagated: {e}\n")

        # Test 3: No error (normal completion)
        print("Test 3: Normal completion (no errors)")
        should_retry = False
        recorded_errors = []
        async with agent.mode("resilient_tracked"):
            agent.mode.state["attempts"] += 1
            print("  Work completed successfully")
        print(f"  Errors recorded: {recorded_errors}")


if __name__ == "__main__":
    asyncio.run(main())
