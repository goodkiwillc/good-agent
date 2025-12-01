import asyncio
from datetime import datetime

from good_agent import Agent


async def main():
    async with Agent("Dynamic assistant") as agent:

        @agent.modes("dynamic")
        async def dynamic_mode(agent: Agent):
            """Mode with dynamic system messages based on state."""

            # Get mode state via agent.mode.state
            user_expertise = agent.mode.state.get("user_expertise", "beginner")
            preferred_style = agent.mode.state.get("preferred_style", "conversational")
            session_length = agent.mode.state.get("session_length", "short")

            # Build dynamic system message
            system_parts = ["You are a helpful assistant."]

            if user_expertise == "expert":
                system_parts.append(
                    "The user is an expert - use technical language and skip basic explanations."
                )
            elif user_expertise == "beginner":
                system_parts.append(
                    "The user is a beginner - explain concepts clearly with examples."
                )

            if preferred_style == "formal":
                system_parts.append("Use formal, professional language.")
            elif preferred_style == "casual":
                system_parts.append("Use casual, friendly language.")

            if session_length == "extended":
                system_parts.append(
                    "This is an extended session - provide comprehensive responses."
                )
            else:
                system_parts.append("Keep responses concise and focused.")

            # Add the dynamic system message via agent.prompt.append()
            agent.prompt.append(" ".join(system_parts))

            # Update session state
            agent.mode.state["last_update"] = datetime.now().isoformat()
            yield agent

        # Configure and use dynamic mode
        async with agent.modes["dynamic"]:
            # Configure user preferences
            agent.modes.set_state("user_expertise", "expert")
            agent.modes.set_state("preferred_style", "formal")
            agent.modes.set_state("session_length", "extended")

            response = await agent.call("Explain machine learning algorithms")
            print(f"Expert response: {response.content}")
            # Response will be technical, formal, and comprehensive

            # Change preferences mid-session
            agent.modes.set_state("user_expertise", "beginner")
            agent.modes.set_state("preferred_style", "casual")

            response = await agent.call("What about neural networks?")
            print(f"Beginner response: {response.content}")
            # Response will be beginner-friendly and casual


if __name__ == "__main__":
    asyncio.run(main())
