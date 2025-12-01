import asyncio

from good_agent import Agent


async def main():
    async with Agent("Routing assistant") as agent:

        @agent.modes("intake")
        async def intake_mode(agent: Agent):
            """Initial intake mode that routes to specialized modes."""
            agent.prompt.append("Determine the user's needs and route appropriately.")
            yield agent

            # Analyze the user's request and decide next mode (in cleanup phase)
            user_intent = agent.mode.state.get("user_intent", "unknown")

            if "research" in user_intent.lower():
                agent.modes.schedule_mode_switch("research")
            elif "creative" in user_intent.lower():
                agent.modes.schedule_mode_switch("creative")
            elif "technical" in user_intent.lower():
                agent.modes.schedule_mode_switch("technical")
            else:
                agent.modes.schedule_mode_exit()

        @agent.modes("technical")
        async def technical_mode(agent: Agent):
            """Technical analysis mode."""
            agent.prompt.append(
                "Provide detailed technical analysis with code examples."
            )
            agent.mode.state["analysis_complete"] = True
            yield agent

            # After technical response, switch to review mode
            agent.mode.state["analysis_topic"] = agent.mode.state.get("topic")
            agent.modes.schedule_mode_switch("review")

        @agent.modes("review")
        async def review_mode(agent: Agent):
            """Review and summarization mode."""
            topic = agent.mode.state.get("analysis_topic", "the analysis")
            agent.prompt.append(f"Provide a concise review and summary of {topic}.")
            yield agent

            # After review, exit back to normal mode
            agent.modes.schedule_mode_exit()

        # Usage - modes will automatically transition
        async with agent.modes["intake"]:
            agent.modes.set_state("user_intent", "technical analysis")

            # This will trigger: intake -> technical -> review -> normal
            # Note: In a real scenario, this would happen over multiple calls
            # unless the mode switch happens immediately without returning response
            # Here intake switches immediately, technical handles one call then switches
            response = await agent.call("Analyze this Python code performance")
            print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
