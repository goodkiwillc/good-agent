import asyncio
from good_agent import Agent

async def main():
    async with Agent(
        "You are in {{location}} helping with {{task}}", 
        context={"location": "Paris", "task": "travel planning"}
    ) as agent:
        # System prompt renders as: "You are in Paris helping with travel planning"
        print(f"System prompt: {agent[0].content}")
        
        agent.append("The weather in {{location}} is {{weather}}", 
                     context={"weather": "sunny"})
        # Message renders as: "The weather in Paris is sunny"
        print(f"Message: {agent[-1].content}")

if __name__ == "__main__":
    asyncio.run(main())
