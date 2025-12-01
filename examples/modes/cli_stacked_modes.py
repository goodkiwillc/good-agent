"""Stacked modes demo for CLI testing.

Run interactively: good-agent run examples/modes/cli_stacked_modes.py
Run demo: python examples/modes/cli_stacked_modes.py

Demonstrates:
- Mode stacking (nested modes)
- State inheritance (inner modes can read outer state)
- State scoping (inner mode writes don't affect outer)
- Mode stack inspection
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
async def set_project_context(
    language: str = "python",
    framework: str = "none",
    *,
    agent: Agent,
) -> str:
    """Set the project context details.

    Args:
        language: Programming language (python, javascript, etc.)
        framework: Framework if any (django, react, etc.)
    """
    agent.mode.state["language"] = language
    agent.mode.state["framework"] = framework
    agent.console.info(f"Project context: {language}, framework: {framework}")
    return f"Project context set: {language}" + (
        f" with {framework}" if framework != "none" else ""
    )


@tool
async def set_feature(name: str, agent: Agent) -> str:
    """Set the current feature being worked on.

    Args:
        name: Name of the feature
    """
    agent.mode.state["feature_name"] = name
    agent.console.info(f"Feature: {name}")
    return f"Working on feature: {name}"


@tool
async def log_issue(issue: str, agent: Agent) -> str:
    """Log an issue found during debugging.

    Args:
        issue: Description of the issue
    """
    if not agent.mode.state.get("debug_active"):
        return "Enter debug mode first to log issues."

    issues = agent.mode.state.get("issues_found", [])
    issues.append(issue)
    agent.mode.state["issues_found"] = issues
    agent.console.warning(f"Issue: {issue}")
    return f"Issue logged: {issue}"


@tool
async def add_review_note(note: str, agent: Agent) -> str:
    """Add a code review note.

    Args:
        note: The review note to add
    """
    if not agent.mode.state.get("review_active"):
        return "Enter review mode first to add notes."

    notes = agent.mode.state.get("review_notes", [])
    notes.append(note)
    agent.mode.state["review_notes"] = notes
    agent.console.info(f"Review note: {note}")
    return f"Review note added: {note}"


@tool
async def show_mode_stack(agent: Agent) -> str:
    """Display the current mode stack and inherited state."""
    if not agent.mode.stack:
        return "No modes active."

    # Use console to display structured data
    agent.console.data(
        {
            "Mode Stack": " > ".join(agent.mode.stack),
            "Current Mode": agent.mode.name,
        },
        title="Mode Status",
    )

    state_data = {k: v for k, v in agent.mode.state.items() if not k.startswith("_")}
    if state_data:
        agent.console.data(state_data, title="Inherited State")

    return f"Mode Stack: {' > '.join(agent.mode.stack)}"


@tool
async def exit_mode(agent: Agent) -> str:
    """Exit the current (topmost) mode."""
    if not agent.mode.name:
        return "No mode to exit."

    mode = agent.mode.name
    remaining = agent.mode.stack[:-1]
    agent.modes.schedule_mode_exit()

    if remaining:
        agent.console.mode_exit(mode, remaining)
        return f"Exiting {mode} mode. Remaining stack: {' > '.join(remaining)}"

    agent.console.mode_exit(mode, [])
    return f"Exiting {mode} mode. Returning to normal operation."


# Create agent
agent = Agent(
    "You are a coding assistant that can operate in different contexts. "
    "You can stack modes to combine behaviors:\n"
    "- 'project' mode: Set project context (language, framework)\n"
    "- 'feature' mode: Work on a specific feature within the project\n"
    "- 'debug' mode: Debugging overlay for troubleshooting\n"
    "- 'review' mode: Code review overlay\n\n"
    "Modes can be stacked - e.g., project > feature > debug means you're "
    "debugging a feature within a project context. "
    "Use 'show_mode_stack' to see current state.",
    model="gpt-4o",
    tools=[
        set_project_context,
        set_feature,
        log_issue,
        add_review_note,
        show_mode_stack,
        exit_mode,
    ],
    name="Code Assistant",
)


# Project mode - base context
@agent.modes("project", invokable=True)
async def project_mode(agent: Agent):
    """Enter project mode to set the working project context."""
    agent.console.mode_enter("project", agent.mode.stack + ["project"])
    agent.prompt.append(
        "\n[PROJECT MODE]\n"
        "You are working within a project context.\n"
        "Use 'set_project_context' to configure language and framework.\n"
        "You can stack 'feature', 'debug', or 'review' modes on top."
    )
    agent.mode.state["context_type"] = "project"
    agent.mode.state["language"] = agent.mode.state.get("language", "python")
    agent.mode.state["framework"] = agent.mode.state.get("framework", "none")
    yield agent


# Feature mode - can stack on project
@agent.modes("feature", invokable=True)
async def feature_mode(agent: Agent):
    """Enter feature mode to work on a specific feature."""
    agent.console.mode_enter("feature", agent.mode.stack + ["feature"])
    language = agent.mode.state.get("language", "unknown")
    framework = agent.mode.state.get("framework", "none")

    agent.prompt.append(
        f"\n[FEATURE MODE]\n"
        f"Working on a feature in {language}"
        f"{f' with {framework}' if framework != 'none' else ''}.\n"
        "Use 'set_feature' to name the current feature.\n"
        "You can stack 'debug' or 'review' modes on top."
    )
    agent.mode.state["context_type"] = "feature"
    agent.mode.state["feature_name"] = agent.mode.state.get("feature_name", "unnamed")
    yield agent


# Debug mode - overlay that can stack on anything
@agent.modes("debug", invokable=True)
async def debug_mode(agent: Agent):
    """Enter debug mode for troubleshooting."""
    agent.console.mode_enter("debug", agent.mode.stack + ["debug"])
    context = agent.mode.state.get("context_type", "none")
    feature = agent.mode.state.get("feature_name", "")

    context_str = ""
    if context == "project":
        context_str = " in project context"
    elif context == "feature":
        context_str = f" for feature: {feature}"

    agent.prompt.append(
        f"\n[DEBUG MODE ACTIVE{context_str}]\n"
        "Debugging overlay enabled:\n"
        "- Use 'log_issue' to record issues found\n"
        "- Focus on identifying and fixing problems"
    )
    agent.mode.state["debug_active"] = True
    agent.mode.state["issues_found"] = []
    yield agent


# Review mode - another overlay
@agent.modes("review", invokable=True)
async def review_mode(agent: Agent):
    """Enter code review mode."""
    agent.console.mode_enter("review", agent.mode.stack + ["review"])
    language = agent.mode.state.get("language", "code")

    agent.prompt.append(
        f"\n[CODE REVIEW MODE]\n"
        f"Reviewing {language} code:\n"
        "- Use 'add_review_note' to record feedback\n"
        "- Check for bugs, best practices, readability"
    )
    agent.mode.state["review_active"] = True
    agent.mode.state["review_notes"] = []
    yield agent


# Demo prompts for end-to-end testing
DEMO_PROMPTS = [
    "Let's start working on a React TypeScript project.",
    "Set the project to use typescript with react framework.",
    "Now I want to work on the authentication feature.",
    "Set the feature name to 'user-authentication'.",
    "Show me the current mode stack.",
    "I'm seeing a bug - let's enter debug mode.",
    "Log this issue: Login form not validating email format correctly",
    "Show the mode stack again.",
    "Exit debug mode and let's do a code review instead.",
    "Add review note: Consider using Zod for form validation",
    "Exit all modes and summarize what we worked on.",
]


async def run_demo(output_format: str = "rich"):
    """Run the demo with predefined prompts."""
    from _cli_utils import configure_console

    configure_console(agent, output_format)  # type: ignore[arg-type]

    async with agent:
        agent.console.section("STACKED MODES DEMO", style="bold cyan")
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
                agent.console.info(f"Mode stack: {' > '.join(agent.mode.stack)}")

            # Show compact token usage after each response
            agent.console.token_usage(compact=True)

        agent.console.newline()
        agent.console.section("Demo Complete", style="bold green")

        # Show full token usage breakdown at the end
        agent.console.token_usage()


if __name__ == "__main__":
    from _cli_utils import parse_output_format

    asyncio.run(run_demo(parse_output_format()))
