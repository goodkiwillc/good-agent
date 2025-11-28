"""Workflow modes demo with automatic transitions for CLI testing.

Run interactively: good-agent run examples/modes/cli_workflow_modes.py
Run demo: python examples/modes/cli_workflow_modes.py

Demonstrates:
- Mode transitions (switch, exit, push)
- Workflow pipelines with sequential modes
- State passing between modes
- Using agent.console for rich CLI output
"""

import asyncio
import logging
from datetime import datetime

from good_agent import Agent, tool

# Suppress noisy LiteLLM logs
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)


# Define tools
@tool
async def advance_workflow(agent: Agent, notes: str = "") -> str:
    """Advance to the next phase of the planning workflow.

    Args:
        notes: Any notes or requirements to carry forward
    """
    current = agent.mode.name

    if not current:
        return "No workflow active. Use 'enter_intake_mode' tool to begin."

    if notes:
        requirements = agent.mode.state.get("requirements", [])
        requirements.append(notes)
        agent.mode.state["requirements"] = requirements
        agent.console.info(f"Added note: {notes[:50]}...")

    if current == "intake":
        agent.console.info("Transitioning: intake -> planning")
        agent.modes.schedule_mode_switch("planning")
        return "Transitioning from intake to planning phase."
    elif current == "planning":
        agent.console.info("Transitioning: planning -> review")
        agent.modes.schedule_mode_switch("review")
        return "Transitioning from planning to review phase."
    elif current == "review":
        agent.console.success("Workflow complete!")
        agent.modes.schedule_mode_exit()
        return "Workflow complete. Exiting review phase."

    return f"Unknown phase: {current}"


@tool
async def add_requirement(requirement: str, agent: Agent) -> str:
    """Add a requirement during the intake phase.

    Args:
        requirement: The requirement to add to the project
    """
    if agent.mode.name != "intake":
        agent.console.warning("Can only add requirements during intake phase")
        return "Can only add requirements during the intake phase."

    requirements = agent.mode.state.get("requirements", [])
    requirements.append(requirement)
    agent.mode.state["requirements"] = requirements
    agent.console.info(f"Requirement added: {requirement}")
    return f"Added requirement: {requirement}"


@tool
async def workflow_status(agent: Agent) -> str:
    """Check the current workflow status and collected information."""
    if not agent.mode.name:
        return "No workflow active."

    phase = agent.mode.state.get("phase", "unknown")
    start = agent.mode.state.get("start_time", "unknown")
    requirements = agent.mode.state.get("requirements", [])
    plan_items = agent.mode.state.get("plan_items", [])

    agent.console.data(
        {"Phase": phase, "Started": start, "Requirements": len(requirements)},
        title="Workflow Status",
    )

    if requirements:
        agent.console.data(requirements, title="Requirements")

    req_str = "\n  ".join(requirements) if requirements else "(none)"
    plan_str = "\n  ".join(plan_items) if plan_items else "(none)"

    return (
        f"Workflow Status:\n"
        f"- Current Phase: {phase}\n"
        f"- Started: {start}\n"
        f"- Requirements:\n  {req_str}\n"
        f"- Plan Items:\n  {plan_str}"
    )


# Create agent with tools
agent = Agent(
    "You are a project planning assistant that helps users through a structured workflow. "
    "The workflow has three phases:\n"
    "1. INTAKE - Gather requirements and understand the project\n"
    "2. PLANNING - Create a detailed plan with milestones\n"
    "3. REVIEW - Summarize and finalize the plan\n\n"
    "Start the planning workflow when the user wants help planning a project. "
    "Use 'advance_workflow' to move between phases.",
    model="gpt-4o",
    tools=[advance_workflow, add_requirement, workflow_status],
    name="Project Planner",
)


# Intake mode - first phase
@agent.modes("intake", invokable=True)
async def intake_mode(agent: Agent):
    """Start the project planning workflow with the intake phase."""
    agent.console.mode_enter("intake", ["intake"])
    agent.console.info("Workflow started - Intake Phase")
    agent.prompt.append(
        "\n[INTAKE PHASE]\n"
        "Gather project requirements. Ask about:\n"
        "- Goals and objectives\n"
        "- Timeline and deadlines\n"
        "- Resources and constraints\n"
        "Use 'add_requirement' to record requirements.\n"
        "Use 'advance_workflow' when ready for planning."
    )
    agent.mode.state["phase"] = "intake"
    agent.mode.state["start_time"] = datetime.now().isoformat()
    agent.mode.state["requirements"] = []


# Planning mode - second phase
@agent.modes("planning")
async def planning_mode(agent: Agent):
    """Planning phase for creating detailed project plans."""
    agent.console.mode_enter("planning", ["planning"])
    requirements = agent.mode.state.get("requirements", [])
    agent.console.info(f"Planning with {len(requirements)} requirements")

    req_str = "\n".join(f"- {r}" for r in requirements) if requirements else "(none)"
    agent.prompt.append(
        f"\n[PLANNING PHASE]\nRequirements:\n{req_str}\n\n"
        "Create a detailed plan with milestones and timeline.\n"
        "Use 'advance_workflow' when ready for review."
    )
    agent.mode.state["phase"] = "planning"
    agent.mode.state["plan_items"] = []


# Review mode - final phase
@agent.modes("review")
async def review_mode(agent: Agent):
    """Review phase for finalizing and summarizing the plan."""
    agent.console.mode_enter("review", ["review"])
    agent.prompt.append(
        "\n[REVIEW PHASE]\n"
        "Summarize the complete project plan.\n"
        "Use 'advance_workflow' to complete the workflow."
    )
    agent.mode.state["phase"] = "review"


# Demo prompts
DEMO_PROMPTS = [
    "I need help planning a mobile app project.",
    "The app should have user authentication, a dashboard, and push notifications. Timeline is 3 months.",
    "Budget is $50k and we have a team of 3 developers.",
    "Let's move to planning now.",
    "What's the current workflow status?",
    "The plan looks good. Let's review and finalize.",
    "Complete the workflow.",
]


async def run_demo(output_format: str = "rich"):
    """Run the demo with predefined prompts."""
    from _cli_utils import configure_console

    configure_console(agent, output_format)  # type: ignore[arg-type]

    async with agent:
        agent.console.section("WORKFLOW MODES DEMO", style="bold cyan")
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
                phase = agent.mode.state.get("phase", "unknown")
                agent.console.info(f"Current phase: {phase}")

        agent.console.newline()
        agent.console.section("Demo Complete", style="bold green")


if __name__ == "__main__":
    from _cli_utils import parse_output_format

    asyncio.run(run_demo(parse_output_format()))
