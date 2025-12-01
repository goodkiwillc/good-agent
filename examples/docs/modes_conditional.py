import asyncio

from good_agent import Agent


async def main():
    async with Agent("Adaptive assistant") as agent:

        @agent.modes("adaptive")
        async def adaptive_mode(agent: Agent):
            """Mode that adapts based on conversation context."""

            # Analyze conversation history
            message_count = len(agent.messages)
            user_messages = len(agent.user)

            # Adapt behavior based on conversation length
            if user_messages < 3:
                agent.prompt.append(
                    "Early conversation - be welcoming and establish rapport."
                )
                agent.mode.state["conversation_phase"] = "greeting"

            elif user_messages < 10:
                agent.prompt.append(
                    "Mid conversation - be helpful and focused on user needs."
                )
                agent.mode.state["conversation_phase"] = "working"

            else:
                agent.prompt.append(
                    "Extended conversation - check if user needs summary or wrap-up."
                )
                agent.mode.state["conversation_phase"] = "concluding"

            # Store conversation metrics
            agent.mode.state["message_count"] = message_count
            agent.mode.state["engagement_level"] = (
                "high" if user_messages > 5 else "normal"
            )
            yield agent

            # Consider transitioning to summary mode (in cleanup phase)
            if agent.mode.state.get("should_summarize", False):
                agent.modes.schedule_mode_switch("summary")

        @agent.modes("summary")
        async def summary_mode(agent: Agent):
            """Summarization mode for long conversations."""
            agent.prompt.append(
                "Provide a helpful summary of our conversation and key takeaways."
            )
            yield agent
            agent.modes.schedule_mode_exit()  # Return to normal after summary

        # Usage
        async with agent.modes["adaptive"]:
            # Simulate conversation
            for i in range(12):
                # In real usage we'd append user messages and call
                agent.append(f"Message number {i + 1}", role="user")
                pass

            # To make this runnable and meaningful without 12 API calls:
            print("Adaptive mode setup complete")


if __name__ == "__main__":
    asyncio.run(main())
