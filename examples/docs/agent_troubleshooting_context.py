import asyncio
from good_agent import Agent


async def main():
    async with Agent("Assistant", context={"env": "prod"}) as agent:
        # Check context resolution
        # Use as_dict() for cleaner access to context content
        print("Current context:", agent.context.as_dict())

        # Debug template rendering
        agent.append("Test {{undefined_var}}")  # May warn about undefined variables


if __name__ == "__main__":
    asyncio.run(main())
