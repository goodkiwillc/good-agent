import asyncio

from good_agent import Agent


async def background_monitor():
    """Simulated background task."""
    await asyncio.sleep(0.1)
    print("Monitor active")

async def main():
    async with Agent("Assistant") as agent:
        # Create managed task
        agent.create_task(
            background_monitor(),
            name="monitor",
            wait_on_ready=False  # Don't block initialization
        )

        print(f"Active tasks: {agent.task_count}")
        await agent.wait_for_tasks(timeout=5.0)  # Wait for completion

        # Context manager exit automatically cancels tasks

if __name__ == "__main__":
    asyncio.run(main())
