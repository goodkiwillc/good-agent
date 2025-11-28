import asyncio

from good_agent import Agent


async def main():
    async with Agent("Composite assistant") as agent:

        @agent.modes("expert")
        async def expert_mode(agent: Agent):
            """Expert knowledge mode."""
            agent.prompt.append("Provide expert-level, technical responses.")
            agent.mode.state["expertise_level"] = "advanced"

        @agent.modes("teaching")
        async def teaching_mode(agent: Agent):
            """Educational mode."""
            agent.prompt.append("Explain concepts clearly with examples.")
            agent.mode.state["teaching_style"] = "socratic"

        @agent.modes("patient")
        async def patient_mode(agent: Agent):
            """Patient, supportive interaction mode."""
            agent.prompt.append("Be patient and encouraging. Break down complex ideas.")
            agent.mode.state["interaction_style"] = "supportive"

        async with agent.modes["expert"]:
            async with agent.modes["teaching"]:
                async with agent.modes["patient"]:
                    # Agent now combines all three behavioral modes
                    print(f"Mode stack: {agent.mode.stack}")
                    # ["expert", "teaching", "patient"]

                    print(f"In expert mode: {agent.mode.in_mode('expert')}")  # True
                    print(f"In teaching mode: {agent.mode.in_mode('teaching')}")  # True
                    print(f"Current mode: {agent.mode.name}")  # "patient"

                    # Agent will be expert + teaching + patient
                    response = await agent.call("Explain quantum entanglement")
                    print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
