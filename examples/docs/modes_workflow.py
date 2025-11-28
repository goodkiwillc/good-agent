import asyncio
from datetime import datetime

from good_agent import Agent


async def main():
    async with Agent("Workflow assistant") as agent:

        @agent.modes("workflow_start")
        async def workflow_start_mode(agent: Agent):
            """Initialize a multi-step workflow."""
            workflow_id = agent.mode.state.get(
                "workflow_id", f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            agent.mode.state["workflow_id"] = workflow_id
            agent.mode.state["workflow_steps"] = [
                "analyze",
                "design",
                "implement",
                "test",
            ]
            agent.mode.state["current_step"] = 0

            agent.prompt.append(
                f"Starting workflow {workflow_id}. Step 1: Analysis phase."
            )

            # Automatically transition to first step
            return agent.mode.switch("workflow_analyze")

        @agent.modes("workflow_analyze")
        async def workflow_analyze_mode(agent: Agent):
            """Analysis phase of workflow."""
            agent.prompt.append(
                "Analysis mode: Break down requirements and identify key components."
            )

            if agent.mode.state.get("analysis_complete"):
                agent.mode.state["current_step"] = 1
                return agent.mode.switch(
                    "workflow_design", analysis_results=agent.mode.state.get("analysis")
                )

            agent.mode.state["analysis_complete"] = True

        @agent.modes("workflow_design")
        async def workflow_design_mode(agent: Agent):
            """Design phase of workflow."""
            analysis_results = agent.mode.state.get(
                "analysis_results", "previous analysis"
            )
            agent.prompt.append(
                f"Design mode: Create detailed design based on {analysis_results}."
            )

            if agent.mode.state.get("design_complete"):
                agent.mode.state["current_step"] = 2
                return agent.mode.switch("workflow_implement")

            agent.mode.state["design_complete"] = True

        @agent.modes("workflow_implement")
        async def workflow_implement_mode(agent: Agent):
            """Implementation phase of workflow."""
            agent.prompt.append(
                "Implementation mode: Provide concrete implementation steps."
            )

            if agent.mode.state.get("implementation_complete"):
                return agent.mode.switch("workflow_complete")

            agent.mode.state["implementation_complete"] = True

        @agent.modes("workflow_complete")
        async def workflow_complete_mode(agent: Agent):
            """Workflow completion mode."""
            workflow_id = agent.mode.state.get("workflow_id", "unknown")
            agent.prompt.append(
                f"Workflow {workflow_id} complete. Provide summary and next steps."
            )

            return agent.mode.exit()  # Return to normal mode

        # Usage - automatic workflow progression
        async with agent.modes["workflow_start"]:
            agent.modes.set_state("project_type", "web application")

            # This will progress through: start -> analyze -> design -> implement -> complete
            await agent.call("Help me build a task management system")

            workflow_id = agent.modes.get_state("workflow_id")
            current_step = agent.modes.get_state("current_step")
            print(f"Workflow {workflow_id}, Step {current_step}")


if __name__ == "__main__":
    asyncio.run(main())
