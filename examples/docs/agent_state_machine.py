import asyncio

from good_agent import Agent
from good_agent.agent.state import AgentState


async def main():
    async with Agent("Assistant") as agent:
        # During context manager entry
        print(agent.state)  # AgentState.INITIALIZING → AgentState.READY
        print(f"Is ready? {agent.state is AgentState.READY}")

        # During execution
        agent.append("Calculate 2+2")
        async for _message in agent.execute():
            print(agent.state)  # READY → PENDING_RESPONSE → PROCESSING → READY

if __name__ == "__main__":
    asyncio.run(main())
