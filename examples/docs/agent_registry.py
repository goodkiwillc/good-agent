import asyncio
from good_agent import Agent

async def main():
    async with Agent("Assistant", name="support-bot") as agent:
        # Retrieve by ID
        same_agent = Agent.get(agent.id)
        assert same_agent is agent
        
        # Retrieve by name
        named_agent = Agent.get_by_name("support-bot")
        assert named_agent is agent
        print(f"Successfully retrieved agent {agent.name} from registry")

if __name__ == "__main__":
    asyncio.run(main())
