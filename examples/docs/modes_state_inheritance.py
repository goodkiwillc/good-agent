import asyncio

from good_agent import Agent


async def main():
    async with Agent("Stateful assistant") as agent:

        @agent.modes("project")
        async def project_mode(agent: Agent):
            """Project management mode."""
            agent.mode.state["project_name"] = "Website Redesign"
            agent.mode.state["team_size"] = 5
            agent.mode.state["deadline"] = "2024-12-01"
            yield agent

        @agent.modes("planning")
        async def planning_mode(agent: Agent):
            """Planning phase within project mode."""
            # Can access project state via agent.mode.state
            project_name = agent.mode.state.get("project_name", "Unknown")

            agent.prompt.append(
                f"Planning mode for {project_name}. Focus on breaking down "
                f"tasks and timelines for {agent.mode.state.get('team_size')} team members."
            )

            # Set planning-specific state
            agent.mode.state["planning_phase"] = "initial"
            agent.mode.state["tasks"] = []
            yield agent

        async with agent.modes["project"]:
            async with agent.modes["planning"]:
                # Inner mode can see both project and planning state
                await agent.call("What's our first milestone?")

                # State is scoped - planning state shadows project if keys conflict
                print(f"Project: {agent.modes.get_state('project_name')}")
                print(f"Planning: {agent.modes.get_state('planning_phase')}")


if __name__ == "__main__":
    asyncio.run(main())
