"""Customize message rendering for different contexts."""

import asyncio

from good_agent import Agent
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, MessageRenderParams


async def main():
    """Demonstrate custom message rendering."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
        def customize_rendering(ctx: EventContext[MessageRenderParams, list]):
            message = ctx.parameters["message"]
            mode = ctx.parameters["mode"]

            # Add custom rendering for specific message types
            if (
                hasattr(message, "metadata")
                and message.metadata is not None
                and "sensitive" in message.metadata
            ):
                if mode == "display":
                    # Mask sensitive content in display mode
                    ctx.output = ["[REDACTED - Sensitive Content]"]
                # Let normal rendering proceed for LLM mode

        # Create a message with sensitive metadata
        message = agent.append("Secret password: 12345")
        if not hasattr(message, "metadata"):
            message.metadata = {}
        message.metadata["sensitive"] = True

        print("Message added with sensitive metadata")


if __name__ == "__main__":
    asyncio.run(main())
