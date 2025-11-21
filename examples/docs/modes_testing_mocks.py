import pytest
import asyncio
from good_agent import Agent, ModeContext

@pytest.mark.asyncio
async def test_mode_workflow_with_mocks():
    """Test complex mode workflow with mocked LLM responses."""
    agent = Agent("Workflow agent")

    workflow_steps = []

    @agent.modes("step1")
    async def step1_mode(ctx: ModeContext):
        workflow_steps.append("step1")
        return ctx.switch_mode("step2")

    @agent.modes("step2")
    async def step2_mode(ctx: ModeContext):
        workflow_steps.append("step2")
        return ctx.switch_mode("step3")

    @agent.modes("step3")
    async def step3_mode(ctx: ModeContext):
        workflow_steps.append("step3")
        return ctx.exit_mode()

    await agent.initialize()

    # Mock responses for each step
    with agent.mock(
        agent.mock.create("Step 1 response"),
        agent.mock.create("Step 2 response"),
        agent.mock.create("Step 3 response")
    ):
        async with agent.modes["step1"]:
            response = await agent.call("Start workflow")

        # Verify workflow progression
        assert workflow_steps == ["step1", "step2", "step3"]
        assert agent.current_mode is None  # Should exit after step3
        assert "Step 3 response" in response.content

if __name__ == "__main__":
    async def main():
        await test_mode_workflow_with_mocks()
        print("Test passed")
    
    asyncio.run(main())
