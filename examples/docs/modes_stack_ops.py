import asyncio

from good_agent import Agent


async def main():
    async with Agent("Assistant") as agent:

        @agent.modes("research")
        async def research_mode(agent: Agent):
            pass

        async with agent.modes["research"]:
            # Check what modes are active
            available_modes = agent.modes.list_modes()
            print(f"Available modes: {available_modes}")

            # Get current mode information via agent.mode.name
            if agent.mode.name:
                mode_info = agent.modes.get_info(agent.mode.name)
                print(f"Mode: {mode_info['name']}")
                print(f"Description: {mode_info['description']}")

            # Check if specific modes are active via agent.mode.in_mode()
            if agent.mode.in_mode("research"):
                print("Research mode is active somewhere in the stack")

            # View the full mode stack via agent.mode.stack
            print(f"Complete mode stack: {agent.mode.stack}")


if __name__ == "__main__":
    asyncio.run(main())
