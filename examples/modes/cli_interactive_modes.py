"""Interactive modes demo designed for CLI chat testing.

Run interactively: good-agent run examples/modes/cli_interactive_modes.py
Run demo: python examples/modes/cli_interactive_modes.py

Demonstrates:
- Invokable modes that the agent can enter via tool calls
- Mode stacking (nested modes)
- Mode state access and persistence
- Manual mode transitions
- Using agent.console for rich CLI output
"""

import asyncio
import logging

from good_agent import Agent, tool

# Suppress noisy LiteLLM logs
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)


# Define tools
@tool
async def exit_current_mode(agent: Agent) -> str:
    """Exit the current mode and return to normal operation."""
    if not agent.mode.name:
        return "Not currently in any mode."

    mode_name = agent.mode.name
    agent.console.mode_exit(mode_name, agent.mode.stack[:-1])
    agent.modes.schedule_mode_exit()
    return f"Exiting {mode_name} mode. Will return to normal operation."


@tool
async def check_mode_status(agent: Agent) -> str:
    """Check the current mode status and state."""
    if not agent.mode.name:
        agent.console.info("No active mode")
        return "Currently in normal mode (no specialized mode active)."

    # Use console to display structured data
    agent.console.data(
        {"Mode": agent.mode.name, "Stack": " > ".join(agent.mode.stack)},
        title="Mode Status",
    )

    state_data = {k: v for k, v in agent.mode.state.items() if not k.startswith("_")}
    if state_data:
        agent.console.data(state_data, title="Mode State")

    state_str = "\n".join(f"  - {k}: {v}" for k, v in state_data.items())
    return (
        f"Current mode: {agent.mode.name}\n"
        f"Mode stack: {agent.mode.stack}\n"
        f"State:\n{state_str or '  (no state)'}"
    )


# Create agent with tools
agent = Agent(
    "You are a versatile assistant with multiple operational modes. "
    "You can switch between modes based on user needs. "
    "Use your mode-switching tools to enter specialized modes when appropriate:\n"
    "- Use 'research' mode for deep investigation and fact-finding\n"
    "- Use 'creative' mode for brainstorming and creative writing\n"
    "- Use 'analysis' mode for data analysis and logical reasoning\n"
    "When in a mode, mention which mode you're in at the start of your response.",
    model="gpt-4o",
    tools=[exit_current_mode, check_mode_status],
    name="Multi-Mode Assistant",
)


# Register modes on the agent
@agent.modes("research", invokable=True)
async def research_mode(agent: Agent):
    """Enter research mode for deep investigation and fact-finding."""
    agent.console.mode_enter("research", agent.mode.stack + ["research"])
    agent.prompt.append(
        "\n[RESEARCH MODE ACTIVE]\n"
        "You are now in research mode. Focus on:\n"
        "- Finding accurate, authoritative information\n"
        "- Citing sources when possible\n"
        "- Providing comprehensive, well-structured responses"
    )
    agent.mode.state["mode_type"] = "research"
    agent.mode.state["queries"] = agent.mode.state.get("queries", [])
    yield agent


@agent.modes("creative", invokable=True)
async def creative_mode(agent: Agent):
    """Enter creative mode for brainstorming and creative writing."""
    agent.console.mode_enter("creative", agent.mode.stack + ["creative"])
    agent.prompt.append(
        "\n[CREATIVE MODE ACTIVE]\n"
        "You are now in creative mode. Focus on:\n"
        "- Generating novel and imaginative ideas\n"
        "- Using vivid language and metaphors\n"
        "- Exploring unconventional perspectives"
    )
    agent.mode.state["mode_type"] = "creative"
    agent.mode.state["ideas_generated"] = 0
    yield agent


@agent.modes("analysis", invokable=True)
async def analysis_mode(agent: Agent):
    """Enter analysis mode for data analysis and logical reasoning."""
    agent.console.mode_enter("analysis", agent.mode.stack + ["analysis"])
    agent.prompt.append(
        "\n[ANALYSIS MODE ACTIVE]\n"
        "You are now in analysis mode. Focus on:\n"
        "- Breaking down problems into components\n"
        "- Using logical, structured reasoning\n"
        "- Providing clear, step-by-step explanations"
    )
    agent.mode.state["mode_type"] = "analysis"
    agent.mode.state["analyses_performed"] = 0
    yield agent


# Demo prompts
DEMO_PROMPTS = [
    "I need to research the history of neural networks. Can you help?",
    "What's the current state of my research?",
    "Now I want to brainstorm some creative applications of AI in art.",
    "Check what mode I'm in now.",
    "Let's switch to analyzing the pros and cons of remote work.",
    "Exit this mode and summarize what we covered.",
]


async def run_demo(output_format: str = "rich"):
    """Run the demo with predefined prompts."""
    from _cli_utils import configure_console

    configure_console(agent, output_format)  # type: ignore[arg-type]

    async with agent:
        agent.console.section("INTERACTIVE MODES DEMO", style="bold cyan")
        agent.console.info(f"Agent: {agent.name}")
        agent.console.rule()

        for i, prompt in enumerate(DEMO_PROMPTS, 1):
            agent.console.newline()
            agent.console.step(f"Prompt: {prompt}", step=i, total=len(DEMO_PROMPTS))
            agent.console.rule()

            response = await agent.call(prompt)

            agent.console.panel(
                str(response.content),
                title="Assistant Response",
                style="green",
                markdown=True,
            )

            if agent.mode.stack:
                agent.console.info(f"Mode: {agent.mode.name}")

        agent.console.newline()
        agent.console.section("Demo Complete", style="bold green")


if __name__ == "__main__":
    from _cli_utils import parse_output_format

    asyncio.run(run_demo(parse_output_format()))
