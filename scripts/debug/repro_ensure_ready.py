
import asyncio
import logging
from good_agent.agent.core import Agent, ensure_ready
from good_agent.core.event_router import on

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MyAgent(Agent):
    @ensure_ready
    async def my_method(self):
        logger.info("my_method executed")
        return "done"

async def slow_task():
    logger.info("Task started")
    await asyncio.sleep(1)
    logger.info("Task finished")

async def main():
    agent = MyAgent(model="gpt-4o-mini")
    await agent.initialize()
    logger.info("Agent initialized")

    # 1. Create a background task that is NOT wait_on_ready (since we are already ready)
    # Actually wait_on_ready only affects initialize().
    
    # Let's create a task
    agent.create_task(slow_task(), name="slow_task", wait_on_ready=False)
    
    # Call my_method. expected: runs immediately, doesn't wait for slow_task
    logger.info("Calling my_method (should be immediate)")
    await agent.my_method()
    logger.info("my_method returned")
    
    # Wait for task to finish so script ends cleanly
    await agent.wait_for_tasks()

if __name__ == "__main__":
    asyncio.run(main())
