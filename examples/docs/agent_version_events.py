import asyncio
from good_agent import Agent
from good_agent.events import AgentEvents

async def main():
    async with Agent("Assistant") as agent:
        @agent.on(AgentEvents.AGENT_VERSION_CHANGE) 
        async def on_version_change(ctx):
            params = ctx.parameters
            print(f"Version changed: {params['old_version']} → {params['new_version']}")
            print(f"Message count: {params['changes']['messages']}")
            
        # Trigger version change
        agent.append("New message")

if __name__ == "__main__":
    asyncio.run(main())
