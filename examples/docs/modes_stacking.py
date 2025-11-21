import asyncio
from good_agent import Agent, ModeContext

async def main():
    async with Agent("Composite assistant") as agent:
        @agent.modes("expert")
        async def expert_mode(ctx: ModeContext):
            """Expert knowledge mode."""
            ctx.add_system_message("Provide expert-level, technical responses.")
            ctx.state["expertise_level"] = "advanced"

        @agent.modes("teaching")
        async def teaching_mode(ctx: ModeContext):
            """Educational mode."""
            ctx.add_system_message("Explain concepts clearly with examples.")
            ctx.state["teaching_style"] = "socratic"

        @agent.modes("patient")
        async def patient_mode(ctx: ModeContext):
            """Patient, supportive interaction mode."""
            ctx.add_system_message("Be patient and encouraging. Break down complex ideas.")
            ctx.state["interaction_style"] = "supportive"

        async with agent.modes["expert"]:
            async with agent.modes["teaching"]:
                async with agent.modes["patient"]:
                    # Agent now combines all three behavioral modes
                    print(f"Mode stack: {agent.mode_stack}")
                    # ["expert", "teaching", "patient"]

                    print(f"In expert mode: {agent.in_mode('expert')}")    # True
                    print(f"In teaching mode: {agent.in_mode('teaching')}")  # True
                    print(f"Current mode: {agent.current_mode}")          # "patient"

                    # Agent will be expert + teaching + patient
                    response = await agent.call("Explain quantum entanglement")
                    print(response.content)

if __name__ == "__main__":
    asyncio.run(main())
