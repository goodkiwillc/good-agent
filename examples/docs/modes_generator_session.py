"""Generator pattern: Session Tracking.

Demonstrates:
- Tracking activity during mode
- Generating summaries on cleanup
- Storing session metrics
"""

import asyncio
from datetime import datetime

from good_agent import Agent


async def main():
    async with Agent("You are a helpful assistant.") as agent:

        @agent.modes("session")
        async def session_mode(agent: Agent):
            """Session tracking mode with activity metrics."""
            # SETUP: Initialize tracking
            agent.mode.state["start_time"] = datetime.now()
            agent.mode.state["queries"] = []
            agent.mode.state["events"] = []
            agent.prompt.append("Session tracking active.")

            print("  [session] Tracking started")
            agent.mode.state["events"].append(("start", datetime.now()))

            yield agent

            # CLEANUP: Generate summary
            duration = datetime.now() - agent.mode.state["start_time"]
            queries = agent.mode.state["queries"]

            agent.mode.state["events"].append(("end", datetime.now()))

            # Store summary for later access
            agent.mode.state["summary"] = {
                "duration_seconds": duration.total_seconds(),
                "query_count": len(queries),
                "queries": queries,
                "events": agent.mode.state["events"],
            }

            print("  [session] Session ended")
            print(f"  [session] Duration: {duration.total_seconds():.3f}s")
            print(f"  [session] Queries: {len(queries)}")

        print("=== Generator Pattern: Session Tracking ===\n")

        # Store summary outside mode scope for access after exit
        session_summary = {}

        @agent.modes("session_with_export")
        async def session_with_export_mode(agent: Agent):
            """Session tracking that exports summary."""
            agent.mode.state["start_time"] = datetime.now()
            agent.mode.state["queries"] = []
            print("  [session] Tracking started")

            yield agent

            duration = datetime.now() - agent.mode.state["start_time"]
            queries = agent.mode.state["queries"]

            # Export summary to outer scope before mode cleanup
            session_summary["duration_seconds"] = duration.total_seconds()
            session_summary["query_count"] = len(queries)
            session_summary["queries"] = list(queries)

            print("  [session] Session ended")
            print(f"  [session] Duration: {duration.total_seconds():.3f}s")
            print(f"  [session] Queries: {len(queries)}")

        async with agent.mode("session_with_export"):
            print(f"  Mode: {agent.mode.name}")

            # Simulate some activity
            agent.mode.state["queries"].append("What is AI?")
            await asyncio.sleep(0.1)  # Simulate work

            agent.mode.state["queries"].append("Tell me about ML")
            await asyncio.sleep(0.1)

            agent.mode.state["queries"].append("Explain neural networks")

            print(f"  Recorded {len(agent.mode.state['queries'])} queries")

        # Access exported summary after mode exit
        print("\n  Session Summary (exported before cleanup):")
        print(f"    Duration: {session_summary['duration_seconds']:.3f}s")
        print(f"    Query count: {session_summary['query_count']}")
        print(f"    Queries: {session_summary['queries']}")


if __name__ == "__main__":
    asyncio.run(main())
