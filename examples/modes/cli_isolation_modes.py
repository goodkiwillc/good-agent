"""Isolation modes demo for CLI testing.

Run interactively: good-agent run examples/modes/cli_isolation_modes.py
Run demo: python examples/modes/cli_isolation_modes.py

Demonstrates:
- Isolation levels: none, config, thread, fork
- How different isolation levels affect state persistence
- Sandbox mode for safe experimentation
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
async def save_sandbox_result(result: str, agent: Agent) -> str:
    """Save a result from sandbox mode.

    Args:
        result: The result to save
    """
    agent.mode.state["saved_result"] = result
    agent.console.success(f"Result saved: {result[:50]}...")
    return f"Result saved to mode state: {result[:100]}..."


@tool
async def isolation_status(agent: Agent) -> str:
    """Check the current isolation level and mode status."""
    if not agent.mode.name:
        agent.console.info("No active mode")
        return "Not in any mode. Normal operation (no isolation)."

    isolation = agent.mode.state.get("isolation_type", "unknown")
    saved = agent.mode.state.get("saved_result", None)

    behavior = {
        "fork": "Complete isolation - nothing persists",
        "thread": "Message isolation - original preserved, new kept",
        "config": "Config isolation - tools isolated, messages shared",
        "none": "No isolation - all changes persist",
    }

    agent.console.data(
        {
            "Mode": agent.mode.name,
            "Isolation": isolation,
            "Behavior": behavior.get(isolation, "unknown"),
            "Duration": f"{agent.mode.duration.total_seconds():.1f}s",
        },
        title="Isolation Status",
    )

    if saved:
        agent.console.info(f"Saved result: {saved[:50]}...")

    return f"Mode: {agent.mode.name}, Isolation: {isolation}"


@tool
async def add_test_note(note: str, agent: Agent) -> str:
    """Add a test note to demonstrate isolation behavior.

    Args:
        note: The note to add
    """
    notes = agent.mode.state.get("test_notes", [])
    notes.append(note)
    agent.mode.state["test_notes"] = notes
    agent.console.info(f"Note added: {note}")
    return f"Note added: {note}"


@tool
async def view_test_notes(agent: Agent) -> str:
    """View all test notes in current mode scope."""
    notes = agent.mode.state.get("test_notes", [])
    if not notes:
        return "No test notes in current scope."
    agent.console.data(notes, title="Test Notes")
    return "Test Notes:\n" + "\n".join(f"- {n}" for n in notes)


@tool
async def exit_mode(agent: Agent) -> str:
    """Exit the current mode (observe isolation effects)."""
    if not agent.mode.name:
        return "No mode to exit."

    mode = agent.mode.name
    isolation = agent.mode.state.get("isolation_type", "none")
    saved = agent.mode.state.get("saved_result")

    agent.console.mode_exit(mode, agent.mode.stack[:-1])
    agent.modes.schedule_mode_exit()

    msg = f"Exiting {mode} mode (isolation: {isolation})."
    if saved:
        msg += f"\nSaved result: {saved[:50]}..."
    if isolation == "fork":
        msg += "\nAll changes will be discarded."

    return msg


# Create agent
agent = Agent(
    "You are an assistant with different isolation modes:\n\n"
    "- 'sandbox' (fork): Complete isolation - nothing persists\n"
    "- 'draft' (thread): Messages temporary, new ones kept\n"
    "- 'experiment' (config): Tools isolated, messages shared\n"
    "- 'normal' (none): Full persistence\n\n"
    "Use sandbox for experiments, draft for temporary work.",
    model="gpt-4o",
    tools=[
        save_sandbox_result,
        isolation_status,
        add_test_note,
        view_test_notes,
        exit_mode,
    ],
    name="Isolation Demo",
)


# Sandbox mode - complete fork isolation
@agent.modes("sandbox", isolation="fork", invokable=True)
async def sandbox_mode(agent: Agent):
    """Enter sandbox mode with complete isolation (fork)."""
    agent.console.mode_enter("sandbox", ["sandbox"])
    agent.console.warning("FORK ISOLATION: Nothing persists!")
    agent.prompt.append(
        "\n[SANDBOX MODE - Full Isolation]\n"
        "You are in a fully isolated sandbox.\n"
        "Nothing persists when you exit.\n"
        "Use 'save_sandbox_result' to store results."
    )
    agent.mode.state["isolation_type"] = "fork"
    agent.mode.state["sandbox_active"] = True


# Draft mode - thread isolation
@agent.modes("draft", isolation="thread", invokable=True)
async def draft_mode(agent: Agent):
    """Enter draft mode with message isolation (thread)."""
    agent.console.mode_enter("draft", ["draft"])
    agent.console.info("THREAD ISOLATION: Original messages preserved")
    agent.prompt.append(
        "\n[DRAFT MODE - Message Isolation]\n"
        "Original conversation preserved.\n"
        "New messages are added on exit."
    )
    agent.mode.state["isolation_type"] = "thread"
    agent.mode.state["draft_mode_active"] = True


# Experiment mode - config isolation
@agent.modes("experiment", isolation="config", invokable=True)
async def experiment_mode(agent: Agent):
    """Enter experiment mode with config isolation."""
    agent.console.mode_enter("experiment", ["experiment"])
    agent.console.info("CONFIG ISOLATION: Tools isolated, messages shared")
    agent.prompt.append(
        "\n[EXPERIMENT MODE - Config Isolation]\n"
        "Messages are shared with parent.\n"
        "Tool configuration is isolated."
    )
    agent.mode.state["isolation_type"] = "config"
    agent.mode.state["experiment_active"] = True


# Normal mode - no isolation
@agent.modes("normal", isolation="none", invokable=True)
async def normal_mode(agent: Agent):
    """Enter normal mode with no isolation."""
    agent.console.mode_enter("normal", ["normal"])
    agent.console.info("NO ISOLATION: All changes persist")
    agent.prompt.append(
        "\n[NORMAL MODE - No Isolation]\nAll messages and config persist."
    )
    agent.mode.state["isolation_type"] = "none"


# Demo prompts
DEMO_PROMPTS = [
    "Let's test sandbox mode - enter it now.",
    "Add a test note: This is a sandbox experiment",
    "Check the isolation status.",
    "Save this result: Sandbox test successful - formula X works",
    "Exit sandbox mode.",
    "Now let's try draft mode for some temporary work.",
    "Add a test note: Draft note that should persist",
    "Check isolation status again.",
    "Exit draft mode and tell me what isolation modes are available.",
]


async def run_demo(output_format: str = "rich"):
    """Run the demo with predefined prompts."""
    from _cli_utils import configure_console

    configure_console(agent, output_format)  # type: ignore[arg-type]

    async with agent:
        agent.console.section("ISOLATION MODES DEMO", style="bold cyan")
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

            if agent.mode.name:
                isolation = agent.mode.state.get("isolation_type", "unknown")
                agent.console.info(f"Mode: {agent.mode.name} ({isolation})")

        agent.console.newline()
        agent.console.section("Demo Complete", style="bold green")


if __name__ == "__main__":
    from _cli_utils import parse_output_format

    asyncio.run(run_demo(parse_output_format()))
