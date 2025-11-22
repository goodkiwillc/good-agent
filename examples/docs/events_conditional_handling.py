"""Use predicates to filter which events to handle."""

import asyncio

from good_agent import Agent
from good_agent.events import AgentEvents


def only_user_messages(ctx):
    """Predicate to only handle user messages."""
    message = ctx.parameters.get("message")
    return message and message.role == "user"


async def main():
    """Demonstrate conditional event handling with predicates."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, predicate=only_user_messages)
        def handle_user_messages(ctx):
            message = ctx.parameters["message"]
            print(f"User said: {message.content}")

        # These will trigger the handler
        agent.append("Hello!")  # user message
        agent.append("How are you?")  # user message

        # This won't trigger the handler
        agent.append("I'm fine, thanks!", role="assistant")


if __name__ == "__main__":
    asyncio.run(main())
