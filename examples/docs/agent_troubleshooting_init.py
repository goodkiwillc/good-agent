import asyncio
from good_agent import Agent

async def main():
    # ❌ Not waiting for initialization
    agent = Agent("Assistant") 
    # await agent.call("Hello")  # May fail if not ready

    # ✅ Proper initialization
    async with Agent("Assistant") as agent:
        await agent.call("Hello")
        
    # ✅ Manual initialization with error handling
    agent = Agent("Assistant")
    try:
        await agent.initialize() # Blocks until READY state
        # await agent.initialize(timeout=10.0) # Can also set timeout
        await agent.call("Hello")
    except TimeoutError:
        print("Agent failed to initialize")
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
