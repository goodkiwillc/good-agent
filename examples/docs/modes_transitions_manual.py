import asyncio
from good_agent import Agent, ModeContext

async def main():
    async with Agent("Routing assistant") as agent:
        @agent.modes("intake")
        async def intake_mode(ctx: ModeContext):
            """Initial intake mode that routes to specialized modes."""
            ctx.add_system_message("Determine the user's needs and route appropriately.")

            # Analyze the user's request and decide next mode
            user_intent = ctx.state.get("user_intent", "unknown")

            if "research" in user_intent.lower():
                return ctx.switch_mode("research")
            elif "creative" in user_intent.lower():
                return ctx.switch_mode("creative")
            elif "technical" in user_intent.lower():
                return ctx.switch_mode("technical")
            else:
                return ctx.exit_mode()  # Go back to normal mode

        @agent.modes("technical")
        async def technical_mode(ctx: ModeContext):
            """Technical analysis mode."""
            ctx.add_system_message("Provide detailed technical analysis with code examples.")

            # After one technical response, switch to review mode
            if ctx.state.get("analysis_complete"):
                return ctx.switch_mode("review", analysis_topic=ctx.state.get("topic"))

            ctx.state["analysis_complete"] = True

        @agent.modes("review")
        async def review_mode(ctx: ModeContext):
            """Review and summarization mode."""
            topic = ctx.state.get("analysis_topic", "the analysis")
            ctx.add_system_message(f"Provide a concise review and summary of {topic}.")

            # After review, exit back to normal mode
            return ctx.exit_mode()

        # Usage - modes will automatically transition
        async with agent.modes["intake"]:
            agent.modes.set_state("user_intent", "technical analysis")

            # This will trigger: intake → technical → review → normal
            # Note: In a real scenario, this would happen over multiple calls
            # unless the mode switch happens immediately without returning response
            # Here intake switches immediately, technical handles one call then switches
            response = await agent.call("Analyze this Python code performance")
            print(response.content)

if __name__ == "__main__":
    asyncio.run(main())
