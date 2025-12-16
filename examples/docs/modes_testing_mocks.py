import asyncio

import pytest

from good_agent import Agent


@pytest.mark.asyncio
async def test_mode_workflow_with_mocks():
    """Test complex mode workflow with mocked LLM responses using v2 API."""
    agent = Agent("Workflow agent")

    workflow_steps = []

    @agent.modes("step1")
    async def step1_mode(agent: Agent):
        workflow_steps.append("step1")
        yield agent
        agent.modes.schedule_mode_switch("step2")

    @agent.modes("step2")
    async def step2_mode(agent: Agent):
        workflow_steps.append("step2")
        yield agent
        agent.modes.schedule_mode_switch("step3")

    @agent.modes("step3")
    async def step3_mode(agent: Agent):
        workflow_steps.append("step3")
        yield agent
        agent.modes.schedule_mode_exit()

    await agent.initialize()

    # Mock responses for each step
    with agent.mock(
        agent.mock.create("Step 1 response"),
        agent.mock.create("Step 2 response"),
        agent.mock.create("Step 3 response"),
    ):
        async with agent.mode("step1"):
            response = await agent.call("Start workflow")

        # Verify workflow progression
        assert workflow_steps == ["step1", "step2", "step3"]
        assert agent.mode.name is None  # Should exit after step3
        assert response.content is not None


async def main():
    await test_mode_workflow_with_mocks()
    print("Test passed")


if __name__ == "__main__":
    asyncio.run(main())
