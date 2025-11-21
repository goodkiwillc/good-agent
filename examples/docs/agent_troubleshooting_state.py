import asyncio
from good_agent import Agent
from good_agent.agent.state import AgentState

async def main():
    async with Agent("Assistant") as agent:
        # Check current state before operations
        if agent.state == AgentState.READY:
            await agent.call("Hello")
        else:
            print(f"Agent not ready: {agent.state}")
            # await agent.wait_for_ready() # wait_for_ready is internal/deprecated usually, initialize() handles it

if __name__ == "__main__":
    asyncio.run(main())
