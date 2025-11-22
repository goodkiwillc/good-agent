"""Track LLM request and response interactions."""

import asyncio

from good_agent import Agent
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, LLMCompleteParams


async def main():
    """Demonstrate LLM interaction monitoring."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.LLM_COMPLETE_BEFORE)
        def before_llm_call(ctx: EventContext[LLMCompleteParams, None]):
            messages = ctx.parameters["messages"]
            model = ctx.parameters["model"]
            temperature = ctx.parameters.get("temperature", "not set")

            print(f"🤖 Calling {model} with {len(messages)} messages")
            print(f"   Temperature: {temperature}")

        @agent.on(AgentEvents.LLM_COMPLETE_AFTER)
        def after_llm_call(ctx: EventContext[LLMCompleteParams, None]):
            response = ctx.parameters.get("response")
            if response:
                print(f"✅ LLM responded with {len(response.content)} characters")

        response = await agent.call("What is 2+2?")
        print(f"\nAgent response: {response}")


if __name__ == "__main__":
    asyncio.run(main())
