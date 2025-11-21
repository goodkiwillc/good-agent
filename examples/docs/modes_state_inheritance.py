import asyncio
from good_agent import Agent, ModeContext

async def main():
    async with Agent("Stateful assistant") as agent:
        @agent.modes("project")
        async def project_mode(ctx: ModeContext):
            """Project management mode."""
            ctx.state["project_name"] = "Website Redesign"
            ctx.state["team_size"] = 5
            ctx.state["deadline"] = "2024-12-01"

        @agent.modes("planning")
        async def planning_mode(ctx: ModeContext):
            """Planning phase within project mode."""
            # Can access project state
            project_name = ctx.state.get("project_name", "Unknown")

            ctx.add_system_message(
                f"Planning mode for {project_name}. Focus on breaking down "
                f"tasks and timelines for {ctx.state.get('team_size')} team members."
            )

            # Set planning-specific state
            ctx.state["planning_phase"] = "initial"
            ctx.state["tasks"] = []

        async with agent.modes["project"]:
            async with agent.modes["planning"]:
                # Inner mode can see both project and planning state
                response = await agent.call("What's our first milestone?")

                # State is scoped - planning state shadows project if keys conflict
                print(f"Project: {agent.modes.get_state('project_name')}")
                print(f"Planning: {agent.modes.get_state('planning_phase')}")

if __name__ == "__main__":
    asyncio.run(main())
