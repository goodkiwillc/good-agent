from typing import cast

import pytest
from litellm.types.completion import ChatCompletionMessageParam
from litellm.types.utils import Choices
from pydantic import BaseModel

from good_agent import Agent
from good_agent.messages import AssistantMessage
from good_agent.model.llm import LanguageModel, StreamChunk


class WeatherInfo(BaseModel):
    """Structured response model for weather extraction."""

    temperature: int
    condition: str
    location: str


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_complete_with_real_api(llm_vcr):
    """Test complete method with real API call via VCR."""
    # Create agent with custom language model
    lm = LanguageModel(model="gpt-4o-mini", temperature=0.5)
    async with Agent(
        "You are a helpful assistant", model="gpt-4o-mini", language_model=lm
    ) as agent:
        # Get the language model from agent
        lm = agent.model  # or agent[LanguageModel]

        # Create messages
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Say hello in exactly 5 words"},
        ]

        # Make completion request
        response = await lm.complete(messages)

        # Verify response structure
        assert response is not None
        assert hasattr(response, "choices")
        assert len(response.choices) > 0
        first_choice = response.choices[0]
        assert hasattr(first_choice, "message")
        message_choice = cast(Choices, first_choice)
        assert message_choice.message.content is not None

        # Verify usage tracking
        assert lm.total_tokens > 0
        assert lm.last_usage is not None
        assert lm.last_usage.total_tokens > 0

        # Verify request/response tracking
        assert len(lm.api_requests) == 1
        assert len(lm.api_responses) == 1


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_stream_with_real_api(llm_vcr):
    """Test streaming functionality with real API call via VCR."""
    lm = LanguageModel(model="gpt-4o-mini", temperature=0.5)
    async with Agent(
        "You are a helpful assistant", model="gpt-4o-mini", language_model=lm
    ) as agent:
        # Get the language model from agent
        lm = agent.model

        # Create messages
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Count from 1 to 5"},
        ]

        # Stream completion
        chunks_received = []
        full_content = ""
        has_finish_reason = False

        async for chunk in lm.stream(messages):
            chunks_received.append(chunk)
            if chunk.content:
                full_content += chunk.content
            if chunk.finish_reason:
                has_finish_reason = True

        # Verify we received multiple chunks
        assert len(chunks_received) > 1, "Should receive multiple chunks when streaming"

        # Verify chunk structure
        for chunk in chunks_received:
            assert isinstance(chunk, StreamChunk)

        # At least one chunk should have a finish_reason
        assert has_finish_reason, "At least one chunk should have finish_reason"

        # Verify full content was assembled
        assert len(full_content) > 0
        # More flexible check - the model should produce something about counting
        assert any(str(i) in full_content for i in range(1, 6)), (
            "Should contain at least one number from 1-5"
        )

        # Verify request tracking
        assert len(lm.api_requests) == 1
        assert len(lm.api_stream_responses) == len(chunks_received)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_extract_with_real_api(llm_vcr):
    """Test structured extraction with real API call via VCR."""
    pytest.importorskip("instructor", reason="instructor module required for extract test")
    lm = LanguageModel(model="gpt-4o-mini", temperature=0)
    async with Agent(
        "You are a weather assistant", model="gpt-4o-mini", language_model=lm
    ) as agent:
        # Get the language model from agent
        lm = agent.model

        # Create messages
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are a weather assistant"},
            {
                "role": "user",
                "content": "The weather in Paris is 22 degrees and sunny today.",
            },
        ]

        # Extract structured data
        result = await lm.extract(messages, WeatherInfo)

        # Verify extraction
        assert isinstance(result, WeatherInfo)
        assert result.temperature == 22
        assert result.condition.lower() == "sunny"
        assert result.location.lower() == "paris"

        # Verify request tracking
        assert len(lm.api_requests) == 1
        assert len(lm.api_responses) == 1


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_fallback_models_with_real_api(llm_vcr):
    """Test fallback model functionality with VCR.

    Note: This test uses a valid model without fallback since
    VCR doesn't play well with invalid model names.
    """
    lm = LanguageModel(
        model="gpt-4o-mini",  # Use valid model for VCR
        temperature=0.5,
    )
    async with Agent("You are helpful", model="gpt-4o-mini", language_model=lm) as agent:
        # Get the language model from agent
        lm = agent.model

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Say 'test successful'"},
        ]

        # Should succeed
        response = await lm.complete(messages)

        assert response is not None
        first_choice = response.choices[0]
        assert hasattr(first_choice, "message")
        message_choice = cast(Choices, first_choice)
        content = message_choice.message.content or ""
        assert "test" in content.lower() or "successful" in content.lower()


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_usage_tracking_across_calls(llm_vcr):
    """Test that usage is properly accumulated across multiple API calls."""
    lm = LanguageModel(model="gpt-4o-mini", temperature=0.5)
    async with Agent("You are helpful", model="gpt-4o-mini", language_model=lm) as agent:
        lm = agent.model

        # First call
        messages1: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Say 'first'"},
        ]
        await lm.complete(messages1)

        first_tokens = lm.total_tokens
        first_cost = lm.total_cost

        # Second call
        messages2: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Say 'second'"},
        ]
        await lm.complete(messages2)

        # Verify accumulation
        assert lm.total_tokens > first_tokens
        assert lm.total_cost >= first_cost  # Cost should accumulate
        assert len(lm.api_requests) == 2
        assert len(lm.api_responses) == 2


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_agent_integration_with_real_api(llm_vcr):
    """Test full Agent integration with LanguageModel using real API."""
    async with Agent(
        "You are a helpful assistant who always responds concisely",
        model="gpt-4o-mini",
        temperature=0.5,
    ) as agent:
        # The agent should have LanguageModel auto-installed
        assert agent.model is not None
        assert isinstance(agent.model, LanguageModel)

        # Make a call through the agent
        response = await agent.call("What is 2+2?")

        # Verify response
        assert isinstance(response, AssistantMessage)
        assert "4" in response.content

        # Verify the LanguageModel tracked the call
        assert agent.model.total_tokens > 0
        assert len(agent.model.api_responses) == 1


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_streaming_through_agent(llm_vcr):
    """Test streaming through Agent's language model with real API."""
    async with Agent("You are a helpful assistant", model="gpt-4o-mini", temperature=0.5) as agent:
        # Stream a response through the language model
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Count from 1 to 3"},
        ]

        chunks = []
        async for chunk in agent.model.stream(messages):
            chunks.append(chunk)

        # Verify we got multiple chunks
        assert len(chunks) > 1

        # Reassemble content
        full_content = "".join(chunk.content or "" for chunk in chunks)
        # At least one number should be present
        assert any(str(i) in full_content for i in [1, 2, 3])


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_error_handling_with_vcr(llm_vcr):
    """Test error handling with VCR recording."""
    lm = LanguageModel(model="gpt-4o-mini", temperature=0.5)
    async with Agent("You are helpful", model="gpt-4o-mini", language_model=lm) as agent:
        lm = agent.model

        # Test with valid messages - VCR replay won't trigger real errors
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Test message"},
        ]

        # This should succeed with VCR
        response = await lm.complete(messages)
        assert response is not None

        # In real usage, errors would be tracked in api_errors
        # But with VCR replay, we expect no errors
        assert len(lm.api_errors) == 0


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_model_override_configuration(llm_vcr):
    """Test that model overrides are properly applied."""
    lm = LanguageModel(
        model="gpt-4o-mini",
        temperature=0.9,  # Override temperature
        max_tokens=50,  # Limit response length
    )
    async with Agent("You are helpful", model="gpt-4o-mini", language_model=lm) as agent:
        lm = agent.model

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are helpful"},
            {
                "role": "user",
                "content": "Write a long story",
            },  # Would be long without max_tokens
        ]

        response = await lm.complete(messages)

        # Response should be limited by max_tokens
        first_choice = response.choices[0]
        assert hasattr(first_choice, "message")
        message_choice = cast(Choices, first_choice)
        content = message_choice.message.content or ""
        assert len(content.split()) < 100  # Should be short due to max_tokens limit
