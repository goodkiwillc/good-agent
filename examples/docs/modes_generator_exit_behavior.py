"""Generator mode handler exit behavior control.

Demonstrates:
- ModeExitBehavior enum (CONTINUE, STOP, AUTO)
- Controlling post-exit LLM behavior
- Using agent.mode.set_exit_behavior() in cleanup
"""

import asyncio

from good_agent import Agent, ModeExitBehavior


async def main():
    async with Agent("You are a helpful assistant.") as agent:

        @agent.modes("stop_after_exit")
        async def stop_mode(agent: Agent):
            """Mode that stops execution after exit."""
            agent.prompt.append("Stop mode - will not call LLM after exit.")
            agent.mode.state["queries"] = []

            yield agent

            # Set exit behavior to STOP - don't call LLM after mode exit
            agent.mode.set_exit_behavior(ModeExitBehavior.STOP)
            print("  [stop_mode] Cleanup - set exit behavior to STOP")

        @agent.modes("continue_after_exit")
        async def continue_mode(agent: Agent):
            """Mode that continues execution after exit."""
            agent.prompt.append("Continue mode - will call LLM after exit.")
            agent.mode.state["findings"] = []

            yield agent

            # Set exit behavior to CONTINUE - always call LLM after exit
            agent.mode.set_exit_behavior(ModeExitBehavior.CONTINUE)
            print("  [continue_mode] Cleanup - set exit behavior to CONTINUE")

        @agent.modes("auto_exit")
        async def auto_mode(agent: Agent):
            """Mode that uses AUTO exit behavior (default)."""
            agent.prompt.append("Auto mode - LLM called only if conversation pending.")
            agent.mode.state["data"] = []

            yield agent

            # AUTO is the default - LLM called if last message needs response
            agent.mode.set_exit_behavior(ModeExitBehavior.AUTO)
            print("  [auto_mode] Cleanup - using AUTO exit behavior")

        @agent.modes("conditional_exit")
        async def conditional_mode(agent: Agent):
            """Mode that decides exit behavior based on state."""
            agent.prompt.append("Conditional mode - exit behavior based on results.")
            agent.mode.state["needs_followup"] = False

            yield agent

            # Decide based on what happened during the mode
            if agent.mode.state.get("needs_followup"):
                agent.mode.set_exit_behavior(ModeExitBehavior.CONTINUE)
                print("  [conditional] Needs followup - CONTINUE")
            else:
                agent.mode.set_exit_behavior(ModeExitBehavior.STOP)
                print("  [conditional] No followup needed - STOP")

        print("=== Generator Mode: Exit Behavior Control ===\n")

        print("ModeExitBehavior options:")
        print("  CONTINUE - Always call LLM after mode exit")
        print("  STOP     - Don't call LLM, return control immediately")
        print("  AUTO     - Call LLM only if conversation is pending (default)\n")

        # Demo: STOP behavior
        print("Test 1: STOP exit behavior")
        async with agent.modes["stop_after_exit"]:
            print("  Mode active...")
        print("  Mode exited\n")

        # Demo: CONTINUE behavior
        print("Test 2: CONTINUE exit behavior")
        async with agent.modes["continue_after_exit"]:
            print("  Mode active...")
        print("  Mode exited\n")

        # Demo: AUTO behavior
        print("Test 3: AUTO exit behavior")
        async with agent.modes["auto_exit"]:
            print("  Mode active...")
        print("  Mode exited\n")

        # Demo: Conditional behavior
        print("Test 4: Conditional exit behavior (no followup)")
        async with agent.modes["conditional_exit"]:
            print("  Mode active...")
            # Not setting needs_followup, so STOP will be used
        print("  Mode exited\n")

        print("Test 5: Conditional exit behavior (with followup)")
        async with agent.modes["conditional_exit"]:
            print("  Mode active...")
            agent.mode.state["needs_followup"] = True
        print("  Mode exited")


if __name__ == "__main__":
    asyncio.run(main())
