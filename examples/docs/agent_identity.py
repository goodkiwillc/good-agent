import asyncio
from good_agent import Agent

async def main():
    async with Agent("Assistant") as agent:
        print(f"Agent ID: {agent.id}")           # Unique ULID
        print(f"Session ID: {agent.session_id}") # Conversation session
        print(f"Version ID: {agent.version_id}") # Current state version
        print(f"Name: {agent.name}")             # Optional human-readable name

if __name__ == "__main__":
    asyncio.run(main())
