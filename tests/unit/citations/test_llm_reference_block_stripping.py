import re

import pytest

from good_agent import Agent
from good_agent.content import RenderMode
from good_agent.core.mdxl import MDXL
from good_agent.extensions.citations import CitationManager
from good_agent.resources.editable_mdxl import EditableMDXL
from good_agent.types import URL


@pytest.mark.asyncio
async def test_llm_render_strips_reference_blocks():
    manager = CitationManager()

    async with Agent(extensions=[manager]) as agent:
        agent.append(
            "Text with cite [!CITE_1!]\n\n[!CITE_1!]: [!CITE_1!]\n",
            role="assistant",
            citations=[URL("https://example.com")],
        )

        msg = agent.messages[-1]
        rendered = msg.render(RenderMode.LLM)

        # Should not contain processed or markdown reference blocks
        assert "[!CITE_1!]: [!CITE_1!]" not in rendered
        assert not re.search(r"^\[(\d+)\]:\s*(?:<(.+?)>|(.+))$", rendered, re.MULTILINE)


@pytest.mark.asyncio
async def test_editable_mdxl_read_strips_reference_blocks():
    content = """
<ground-truth>
  Some text [!CITE_1!]

  [!CITE_1!]: [!CITE_1!]
</ground-truth>
"""
    mdxl = MDXL(content)
    resource = EditableMDXL(mdxl)
    await resource.initialize()
    result = await resource.read()
    # Extract string from ToolResponse if needed
    result = result.response if hasattr(result, "response") else str(result)

    # Ensure reference blocks are stripped from tool output
    assert "[!CITE_1!]: [!CITE_1!]" not in result
    assert not re.search(r"^\[(\d+)\]:\s*(?:<(.+?)>|(.+))$", result, re.MULTILINE)
