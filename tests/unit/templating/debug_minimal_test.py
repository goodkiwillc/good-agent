import asyncio

import pytest

# Try importing step by step to isolate the issue


def test_import_step_by_step():
    """Test agent imports step by step."""
    print("Starting import test")

    # Step 1: Import Agent class first
    try:
        from good_agent import Agent

        print("Agent imported successfully")
    except Exception as e:
        print(f"Agent import failed: {e}")
        pytest.fail(f"Agent import failed: {e}")

    # Step 2: Try creating a simple agent
    async def create_agent():
        agent = Agent("Test system", context={"var": "test"})
        await agent.ready()
        await agent.async_close()
        return True

    try:
        result = asyncio.run(create_agent())
        print(f"Agent creation test: {result}")
    except Exception as e:
        print(f"Agent creation failed: {e}")
        pytest.fail(f"Agent creation failed: {e}")


def test_simple_import():
    """Just test the import."""
    from good_agent import Agent

    assert Agent is not None
