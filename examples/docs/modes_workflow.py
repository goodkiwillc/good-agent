import asyncio
from datetime import datetime
from good_agent import Agent, ModeContext

async def main():
    async with Agent("Workflow assistant") as agent:
        @agent.modes("workflow_start")
        async def workflow_start_mode(ctx: ModeContext):
            """Initialize a multi-step workflow."""
            workflow_id = ctx.state.get("workflow_id", f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            ctx.state["workflow_id"] = workflow_id
            ctx.state["workflow_steps"] = ["analyze", "design", "implement", "test"]
            ctx.state["current_step"] = 0

            ctx.add_system_message(f"Starting workflow {workflow_id}. Step 1: Analysis phase.")

            # Automatically transition to first step
            return ctx.switch_mode("workflow_analyze")

        @agent.modes("workflow_analyze")
        async def workflow_analyze_mode(ctx: ModeContext):
            """Analysis phase of workflow."""
            ctx.add_system_message("Analysis mode: Break down requirements and identify key components.")

            if ctx.state.get("analysis_complete"):
                ctx.state["current_step"] = 1
                return ctx.switch_mode("workflow_design", analysis_results=ctx.state.get("analysis"))

            ctx.state["analysis_complete"] = True

        @agent.modes("workflow_design")
        async def workflow_design_mode(ctx: ModeContext):
            """Design phase of workflow."""
            analysis_results = ctx.state.get("analysis_results", "previous analysis")
            ctx.add_system_message(f"Design mode: Create detailed design based on {analysis_results}.")

            if ctx.state.get("design_complete"):
                ctx.state["current_step"] = 2
                return ctx.switch_mode("workflow_implement")

            ctx.state["design_complete"] = True

        @agent.modes("workflow_implement")
        async def workflow_implement_mode(ctx: ModeContext):
            """Implementation phase of workflow."""
            ctx.add_system_message("Implementation mode: Provide concrete implementation steps.")

            if ctx.state.get("implementation_complete"):
                return ctx.switch_mode("workflow_complete")

            ctx.state["implementation_complete"] = True

        @agent.modes("workflow_complete")
        async def workflow_complete_mode(ctx: ModeContext):
            """Workflow completion mode."""
            workflow_id = ctx.state.get("workflow_id", "unknown")
            ctx.add_system_message(f"Workflow {workflow_id} complete. Provide summary and next steps.")

            return ctx.exit_mode()  # Return to normal mode

        # Usage - automatic workflow progression
        async with agent.modes["workflow_start"]:
            agent.modes.set_state("project_type", "web application")

            # This will progress through: start → analyze → design → implement → complete
            await agent.call("Help me build a task management system")

            workflow_id = agent.modes.get_state("workflow_id")
            current_step = agent.modes.get_state("current_step")
            print(f"Workflow {workflow_id}, Step {current_step}")

if __name__ == "__main__":
    asyncio.run(main())
