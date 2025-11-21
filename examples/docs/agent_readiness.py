import asyncio
from good_agent import Agent
from good_agent.agent.core import ensure_ready

# Custom agent extension
class CustomAgent(Agent):
    @ensure_ready
    async def custom_operation(self):
        """This method waits for agent to be ready."""
        return await self.call("Do something")
        
    @ensure_ready(wait_for_tasks=True, timeout=30.0)
    async def careful_operation(self):
        """Wait for agent AND any background tasks."""
        return await self.call("Critical operation")

async def main():
    async with CustomAgent("Assistant") as agent:
        await agent.custom_operation()
        print("Custom operation complete")
        
    # Manual readiness checking
    agent = Agent("Assistant")
    await agent.initialize()
    
    # Check if ready
    if agent.is_ready:
        await agent.call("Hello")
        
    # Wait for readiness
    await agent.initialize()  # Blocks until READY state
    # await agent.wait_for_ready(timeout=10.0)  # With timeout (deprecated in new state machine)
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
