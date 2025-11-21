import os

import pytest
from box import Box
from good_agent import Agent
from good_agent.resources import EditableYAML


def _has_any_llm_key() -> bool:
    return any(
        os.getenv(k)
        for k in (
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
        )
    )


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_editable_yaml_real_llm_edits_with_tools(llm_vcr):
    if not _has_any_llm_key():
        pytest.skip("No LLM API key set; skipping real-LLM integration test")

    initial = """
    meta:
      version: 1.0
    config:
      title: Draft
    """

    resource = EditableYAML(initial, name="doc")

    # Strongly instruct the model to use tools for edits
    async with Agent(
        "You are a YAML editor. Only modify the document via the provided tools."
        " Use the 'set' tool to update values. Return a short confirmation when done.",
        # temperature=0,
    ) as agent:
        async with resource(agent):
            assert isinstance(resource.state, Box)
            assert resource.state.meta.version == 1.0
            assert resource.state.config.title == "Draft"

            # Ask the LLM to perform a concrete edit via tools
            await agent.call(
                "Update meta.version to '3.0' and set config.title to 'Final'. Confirm when done."
            )

            # Verify the resource was actually edited by tool execution
            assert isinstance(resource.state, Box)
            assert resource.state.meta.version == 3.0
            assert resource.state.config.title == "Final"
