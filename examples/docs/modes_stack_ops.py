import asyncio
from good_agent import Agent, ModeContext

async def main():
    async with Agent("Assistant") as agent:
        @agent.modes("research")
        async def research_mode(ctx: ModeContext):
            pass
            
        async with agent.modes["research"]:
            # Check what modes are active
            available_modes = agent.modes.list_modes()
            print(f"Available modes: {available_modes}")

            # Get current mode information
            if agent.current_mode:
                mode_info = agent.modes.get_info(agent.current_mode)
                print(f"Mode: {mode_info['name']}")
                print(f"Description: {mode_info['description']}")

            # Check if specific modes are active
            if agent.in_mode("research"):
                print("Research mode is active somewhere in the stack")

            # View the full mode stack
            print(f"Complete mode stack: {agent.mode_stack}")

if __name__ == "__main__":
    asyncio.run(main())
