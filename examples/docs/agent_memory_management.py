import asyncio
from good_agent import Agent


async def main():
    async with Agent("Long-running assistant") as agent:
        # Simulate many messages
        for i in range(1005):
            agent.append(f"Message {i}")

        # After many interactions...
        if len(agent) > 1000:
            # Keep only recent messages
            recent_messages = agent.messages[-100:]

            # Create new agent with recent context
            # Access underlying context dict properly via as_dict()
            new_agent = Agent(
                agent[0].content,  # Keep system prompt
                context=agent.context.as_dict(),
            )

            # Transfer recent messages
            for msg in recent_messages:
                new_agent.append(msg.content, role=msg.role)

            print(f"Transferred {len(new_agent)} messages to new agent")


if __name__ == "__main__":
    asyncio.run(main())
