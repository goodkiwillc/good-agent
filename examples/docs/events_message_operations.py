"""Intercept and modify message operations."""

import asyncio
from datetime import datetime

from good_agent import Agent
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, MessageAppendParams


async def main():
    """Demonstrate message creation and modification events."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.MESSAGE_APPEND_BEFORE)
        def before_message_append(ctx: EventContext[MessageAppendParams, None]):
            message = ctx.parameters["message"]

            # Add metadata to messages
            if not hasattr(message, "metadata"):
                message.metadata = {}
            message.metadata["timestamp"] = datetime.now().isoformat()
            message.metadata["handler_processed"] = True

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def after_message_append(ctx: EventContext[MessageAppendParams, None]):
            message = ctx.parameters["message"]
            agent_ref = ctx.parameters["agent"]

            # Log message statistics
            total_messages = len(agent_ref.messages)
            print(f"Added {message.role} message. Total: {total_messages}")

        # Append messages to trigger events
        agent.append("Hello!")
        agent.append("How are you?", role="assistant")


if __name__ == "__main__":
    asyncio.run(main())
