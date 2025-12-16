import asyncio

from good_agent.messages import UserMessage


async def main():
    # Text-only message
    user_msg = UserMessage("Hello, how are you?")
    print(f"Text: {user_msg.content}")

    # Multi-part content
    user_msg = UserMessage("Analyze this image", images=["path/to/image.jpg"])
    print(f"Multi-part: {user_msg.content}")

    # With image detail settings
    user_msg = UserMessage(
        "What's in this image?",
        images=["image.jpg"],
        image_detail="high"  # "auto", "low", "high"
    )
    print(f"Detailed: {user_msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
