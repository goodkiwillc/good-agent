import asyncio
from datetime import datetime
from good_agent import Agent, ModeContext

async def main():
    async with Agent("Context-aware assistant") as agent:
        @agent.modes("context_aware")
        async def context_aware_mode(ctx: ModeContext):
            """Mode that analyzes and responds to conversation context."""

            # Access conversation history
            total_messages = len(ctx.agent.messages)
            # Access filtered views
            user_messages = len(ctx.agent.user)
            assistant_messages = len(ctx.agent.assistant)

            # Analyze recent conversation
            recent_topics = []
            for message in ctx.agent.user[-3:]:  # Last 3 user messages
                # Simple topic extraction (in practice, use NLP)
                if "python" in message.content.lower():
                    recent_topics.append("programming")
                elif "ai" in message.content.lower():
                    recent_topics.append("artificial intelligence")

            # Add contextual system message
            ctx.add_system_message(
                f"Context: {total_messages} total messages, recent topics: {recent_topics}. "
                f"Tailor your response to build on this conversation history."
            )

            # Store context analysis
            ctx.state["conversation_length"] = total_messages
            ctx.state["recent_topics"] = recent_topics
            ctx.state["analysis_timestamp"] = datetime.now().isoformat()

        # Usage
        async with agent.modes["context_aware"]:
            # Each call builds on conversation history
            await agent.call("Tell me about Python")
            await agent.call("How does it relate to AI?")
            await agent.call("What's the best framework?")

            # Mode has full context of the conversation
            context = {
                "length": agent.modes.get_state("conversation_length"),
                "topics": agent.modes.get_state("recent_topics"),
                "analyzed": agent.modes.get_state("analysis_timestamp")
            }
            print(f"Context analysis: {context}")

if __name__ == "__main__":
    asyncio.run(main())
