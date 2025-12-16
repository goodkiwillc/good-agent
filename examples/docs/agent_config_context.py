import asyncio

from good_agent import Agent


async def main():
    async with Agent("Assistant", temperature=0.7) as agent:
        # Normal creative temperature
        response1 = await agent.call("Write a story")
        print(f"Response 1: {response1.content}")

        # Temporarily more deterministic
        with agent.config(temperature=0.1, max_tokens=100):
            response2 = await agent.call("Summarize the above")
            print(f"Response 2: {response2.content}")

        # Back to original settings
        response3 = await agent.call("Continue the story")
        print(f"Response 3: {response3.content}")

if __name__ == "__main__":
    asyncio.run(main())
