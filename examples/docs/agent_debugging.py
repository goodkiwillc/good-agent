import asyncio
from good_agent import Agent

async def main():
    async with Agent("Assistant", _event_trace=True) as agent:
        # Enable detailed logging via config if available, or manually set up
        # agent.config.litellm_debug = True # Might not be directly available depending on config
        # agent.config.print_messages_mode = "raw"  # Show raw LLM messages
        
        # Append a message to have something to inspect
        agent.append("Hello")
        
        # Inspect internal state
        print("=== Agent State ===")
        print(f"State: {agent.state}")
        print(f"Version: {agent.version_id}")
        print(f"Messages: {len(agent)}")
        
        # View message history  
        for i, msg in enumerate(agent.messages):
            print(f"{i}: {msg.role} - {msg.content[:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
