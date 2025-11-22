"""Handle streaming LLM responses chunk by chunk."""

import asyncio

from good_agent import Agent
from good_agent.events import AgentEvents


async def main():
    """Demonstrate streaming event handling."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.LLM_STREAM_CHUNK)
        def on_stream_chunk(ctx):
            chunk = ctx.parameters.get("chunk")
            if chunk and hasattr(chunk, "choices"):
                content = chunk.choices[0].delta.content
                if content:
                    print(content, end="", flush=True)

        # Note: Streaming depends on LLM configuration
        response = await agent.call("Tell me a short story", stream=True)
        print(f"\n\nFinal response: {response}")


if __name__ == "__main__":
    asyncio.run(main())
