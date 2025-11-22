import asyncio
from good_agent import Agent

async def main():
    # ❌ Not waiting for initialization
    uninitialized_agent = Agent("Assistant") 
    print(f"Initial state: {uninitialized_agent.state}")
    # await uninitialized_agent.call("Hello")  # May fail if not ready

    # ✅ Proper initialization
    async with Agent("Assistant") as ready_agent:
        await ready_agent.call("Hello")
        
    # ✅ Manual initialization with error handling
    managed_agent = Agent("Assistant")
    try:
        await managed_agent.initialize() # Blocks until READY state
        # await managed_agent.initialize(timeout=10.0) # Can also set timeout
        await managed_agent.call("Hello")
    except TimeoutError:
        print("Agent failed to initialize")
    finally:
        await managed_agent.close()

if __name__ == "__main__":
    asyncio.run(main())
