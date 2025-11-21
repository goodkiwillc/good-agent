import asyncio
from good_agent import Agent

async def main():
    async with Agent("Base prompt", context={"env": "prod", "user": "alice"}) as agent:
        # Override context temporarily
        with agent.context(env="dev", debug=True):
            agent.append("Debug info for {{user}} in {{env}}: {{debug}}")
            # Renders: "Debug info for alice in dev: True"
            print(f"In scope: {agent[-1].content}")
        
        # Back to original context
        agent.append("User {{user}} in {{env}}")  
        # Renders: "User alice in prod"
        print(f"Out of scope: {agent[-1].content}")

if __name__ == "__main__":
    asyncio.run(main())
