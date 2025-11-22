"""Tool composition: calling tools from within other tools."""

import asyncio

from fast_depends import Depends
from good_agent import Agent, tool
from good_agent.tools import ToolContext


@tool
async def analyze_text(text: str) -> dict:
    """Analyze text and return statistics."""
    return {
        "length": len(text),
        "words": len(text.split()),
        "uppercase": sum(1 for c in text if c.isupper()),
    }


@tool
async def summarize_text(text: str) -> str:
    """Summarize text."""
    # Simple truncation for demo
    return text[:100] + "..." if len(text) > 100 else text


@tool
async def process_document(
    text: str, context: ToolContext = Depends(ToolContext)
) -> dict:
    """
    Process document using multiple tools.

    Args:
        text: Document text
        context: Tool context

    Returns:
        Complete analysis
    """
    agent = context.agent

    # Call analysis tool
    analysis_result = await agent.tools["analyze_text"](_agent=agent, text=text)

    # Call summarization tool
    summary_result = await agent.tools["summarize_text"](_agent=agent, text=text)

    return {
        "analysis": analysis_result.response if analysis_result.success else None,
        "summary": summary_result.response if summary_result.success else None,
        "processed": True,
    }


async def main():
    """Demonstrate tool composition."""
    tools = [analyze_text, summarize_text, process_document]
    async with Agent("Document processor", tools=tools) as agent:
        result = await agent.invoke(
            process_document,
            text="This is a sample document for processing and analysis.",
        )
        print(f"Processing result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
