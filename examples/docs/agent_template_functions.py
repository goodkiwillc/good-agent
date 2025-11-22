import asyncio
from datetime import datetime
from good_agent import Agent


# Register global context provider with a custom name
# Note: In a real app, this would likely be in a setup file
# IMPORTANT: Don't override built-in providers like "now" and "today"!
@Agent.context_providers("formatted_time")
def formatted_time():
    """Provide formatted timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def main():
    async with Agent("Current time is {{formatted_time}}") as agent:
        # System prompt includes current timestamp
        print(f"System prompt: {agent[0].content}")

        # Can be used in response too if LLM uses it
        response = await agent.call("What time is it according to your instructions?")
        print(f"Response: {response.content}")


if __name__ == "__main__":
    asyncio.run(main())
