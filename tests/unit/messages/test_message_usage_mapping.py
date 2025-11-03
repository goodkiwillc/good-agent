import pytest
from good_agent.messages import AssistantMessage, Message


@pytest.mark.unit
def test_from_llm_response_maps_top_level_usage_to_message_usage():
    # Simulate an OpenAI/OpenRouter-style top-level response with usage
    api_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1730000000,
        "model": "openrouter/anthropic/claude-3.5-sonnet",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Hello world",
                    "tool_calls": [],
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }

    msg = Message.from_llm_response(api_response, role="assistant")
    assert isinstance(msg, AssistantMessage)
    assert msg.usage is not None, "usage should be set from top-level response"
    assert msg.usage.prompt_tokens == 10
    assert msg.usage.completion_tokens == 5
    assert msg.usage.total_tokens == 15


@pytest.mark.unit
def test_from_llm_response_accepts_inner_message_with_usage():
    # Simulate directly passing the inner message dict (no choices key)
    inner_message = {
        "role": "assistant",
        "content": "Hi there",
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        },
    }

    msg = Message.from_llm_response(inner_message, role="assistant")
    assert isinstance(msg, AssistantMessage)
    assert msg.usage is not None, "usage should be preserved from inner message"
    assert msg.usage.prompt_tokens == 3
    assert msg.usage.completion_tokens == 2
    assert msg.usage.total_tokens == 5
