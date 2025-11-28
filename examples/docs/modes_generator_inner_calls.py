"""Generator mode handler with inner agent calls.

Demonstrates:
- Making agent.call() during setup phase
- Making agent.call() during cleanup phase
- Mode configuration applies to inner calls
"""

import asyncio

from good_agent import Agent


async def main():
    async with Agent("You are a research assistant.") as agent:
        # Store summary outside mode scope for access after exit
        stored_summary = None

        @agent.modes("research")
        async def research_mode(agent: Agent):
            """Research mode with setup and cleanup calls."""
            nonlocal stored_summary
            agent.mode.state["findings"] = []
            agent.prompt.append("Research mode: Focus on thorough investigation.")

            # Setup: initialize research with an LLM call
            print("  [setup] Making initialization call...")
            with agent.mock("[mock] Research initialized. Ready to investigate."):
                init_response = await agent.call("Begin research preparation")
                agent.mode.state["init_message"] = init_response.content
                print(f"  [setup] Init response: {init_response.content}")

            yield agent  # Main research happens here

            # Cleanup: summarize findings with an LLM call
            print("  [cleanup] Making summary call...")
            findings = agent.mode.state.get("findings", [])
            with agent.mock(f"[mock] Summary: Found {len(findings)} key points."):
                summary = await agent.call(f"Summarize findings: {findings}")
                stored_summary = summary.content  # Export to outer scope
                print(f"  [cleanup] Summary: {summary.content}")

        print("=== Generator Mode: Inner Calls ===\n")

        print("Entering research mode (setup will make LLM call)...")
        async with agent.modes["research"]:
            print(f"\n  Mode active: {agent.mode.name}")
            print(f"  Init message: {agent.mode.state['init_message']}")

            # Simulate research activity
            agent.mode.state["findings"].append("Important fact 1")
            agent.mode.state["findings"].append("Important fact 2")
            agent.mode.state["findings"].append("Important fact 3")
            print(f"  Added {len(agent.mode.state['findings'])} findings\n")

        print("\nMode exited")
        print(f"Summary stored: {stored_summary}")


if __name__ == "__main__":
    asyncio.run(main())
