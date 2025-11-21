import asyncio
from good_agent import Agent

async def main():
    async with Agent("Assistant") as agent:
        agent.append("Original message")
        checkpoint = agent.version_id
        
        # Make changes
        agent.append("Unwanted message") 
        agent.append("Another change")
        
        print(f"Messages before: {len(agent)}")  # 3 messages
        
        # Revert to checkpoint (non-destructive)
        agent.revert_to_version(0)  # Version index, not version_id
        print(f"Messages after: {len(agent)}")   # 1 message
        
        # Version ID changes to indicate new state
        assert agent.version_id != checkpoint

if __name__ == "__main__":
    asyncio.run(main())
