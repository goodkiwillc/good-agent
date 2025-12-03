import os

import pytest

from good_agent.messages import AssistantMessage, Message


@pytest.mark.integration
@pytest.mark.vcr
def test_openrouter_usage_is_mapped_with_vcr(llm_vcr):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set; skipping real API test")

    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    resp = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hi"},
        ],
        temperature=0,
    )

    try:
        response_dict = resp.model_dump()
    except Exception:
        import json

        response_dict = json.loads(resp.json()) if hasattr(resp, "json") else dict(resp)

    assert "usage" in response_dict, "API response should include top-level usage"

    msg = Message.from_llm_response(response_dict, role="assistant")
    assert isinstance(msg, AssistantMessage)
    assert msg.usage is not None, "usage should be mapped to message.usage"
    assert msg.usage.total_tokens is not None
