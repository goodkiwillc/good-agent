import os
from typing import cast

import pytest
from good_agent import Agent
from good_agent.model.llm import LanguageModel
from litellm.types.utils import Choices


@pytest.mark.asyncio
@pytest.mark.llm
async def test_simple_vcr_without_agent():
    """Test VCR without agent complexity - direct API call."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY required to run live llm tests")

    import litellm

    # Simple direct litellm call
    response = await litellm.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello"}],
        temperature=0,
    )

    assert response is not None
    assert response.choices[0].message.content is not None
    print(f"Response: {response.choices[0].message.content}")


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_simple_vcr_with_marking(llm_vcr):
    """Test VCR with marking - should use cassette."""
    import litellm

    # Simple direct litellm call
    response = await litellm.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello"}],
        temperature=0,
    )

    assert response is not None
    assert response.choices[0].message.content is not None
    print(f"Response: {response.choices[0].message.content}")


@pytest.mark.asyncio
@pytest.mark.llm
async def test_language_model_without_vcr():
    """Test LanguageModel without VCR to ensure it works."""
    # Skip if no API key
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No OPENAI_API_KEY set")

    # Create a simple language model
    lm = LanguageModel(model="gpt-4o-mini", temperature=0)

    # Create a minimal agent just to install the component
    async with Agent("You are helpful", model="gpt-4o-mini") as agent:
        # Language model is auto-installed
        lm = agent.model

        # Make a simple call
        messages = [{"role": "user", "content": "Say hello"}]
        response = await lm.complete(messages)

        assert response is not None
        first_choice = response.choices[0]
        assert hasattr(first_choice, "message")
        message_choice = cast(Choices, first_choice)
        assert message_choice.message.content is not None
        assert lm.total_tokens > 0

        print(f"Response: {message_choice.message.content}")
        print(f"Tokens used: {lm.total_tokens}")
