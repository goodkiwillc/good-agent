import asyncio
from good_agent import Agent, tool
from good_agent.tools import ToolContext

@tool
async def tool_without_depends(
    ctx: ToolContext
) -> str:
    return f"Agent: {ctx.agent.name}"

async def main():
    agent = Agent("Test Agent", name="test_agent", tools=[tool_without_depends])
    
    print("Testing tool_without_depends (Auto Injection)...")
    try:
        result = await agent.tool_calls.invoke("tool_without_depends")
        print(f"Result: {result.response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
