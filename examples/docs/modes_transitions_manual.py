import asyncio

from good_agent import Agent


async def main():
    async with Agent("Routing assistant") as agent:

        @agent.modes("intake")
        async def intake_mode(agent: Agent):
            """Initial intake mode that routes to specialized modes."""
            agent.prompt.append("Determine the user's needs and route appropriately.")

            # Analyze the user's request and decide next mode
            user_intent = agent.mode.state.get("user_intent", "unknown")

            if "research" in user_intent.lower():
                return agent.mode.switch("research")
            elif "creative" in user_intent.lower():
                return agent.mode.switch("creative")
            elif "technical" in user_intent.lower():
                return agent.mode.switch("technical")
            else:
                return agent.mode.exit()  # Go back to normal mode

        @agent.modes("technical")
        async def technical_mode(agent: Agent):
            """Technical analysis mode."""
            agent.prompt.append(
                "Provide detailed technical analysis with code examples."
            )

            # After one technical response, switch to review mode
            if agent.mode.state.get("analysis_complete"):
                return agent.mode.switch(
                    "review", analysis_topic=agent.mode.state.get("topic")
                )

            agent.mode.state["analysis_complete"] = True

        @agent.modes("review")
        async def review_mode(agent: Agent):
            """Review and summarization mode."""
            topic = agent.mode.state.get("analysis_topic", "the analysis")
            agent.prompt.append(f"Provide a concise review and summary of {topic}.")

            # After review, exit back to normal mode
            return agent.mode.exit()

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
