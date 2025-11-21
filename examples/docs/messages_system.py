import asyncio
from good_agent.messages import SystemMessage

async def main():
    # Basic system message
    system_msg = SystemMessage("You are a helpful assistant.")
    print(f"Basic: {system_msg.content}")

    # With templating
    system_msg = SystemMessage(
        "You are an expert in {{domain}}",
        context={"domain": "machine learning"}
    )
    print(f"Templated: {system_msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
