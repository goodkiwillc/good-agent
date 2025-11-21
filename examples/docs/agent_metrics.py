import asyncio
from good_agent import Agent

async def main():
    async with Agent("Assistant") as agent:
        # Basic metrics
        print(f"Messages: {len(agent)}")
        print(f"Active tasks: {agent.task_count}")
        print(f"State: {agent.state}")
        print(f"Ready: {agent.is_ready}")
        
        # Version history
        # Using internal property for example, though in real apps rely on public API
        print(f"Version count: {agent._version_manager.version_count}")
        print(f"Current version: {len(agent.current_version)} messages")

if __name__ == "__main__":
    asyncio.run(main())
