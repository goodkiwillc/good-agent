import asyncio
from good_agent.messages import AssistantMessage
from good_agent.tools import ToolCall, ToolCallFunction

async def main():
    # Text response
    assistant_msg = AssistantMessage("I'm doing well, thank you!")
    print(f"Text: {assistant_msg.content}")

    # With tool calls
    # Note: ToolCall expects function to be a ToolCallFunction object
    assistant_msg = AssistantMessage(
        "Let me calculate that for you.",
        tool_calls=[
            ToolCall(
                id="call_123", 
                function=ToolCallFunction(
                    name="calculator", 
                    arguments="{}"
                )
            )
        ]
    )
    print(f"With tools: {assistant_msg.tool_calls}")

    # With reasoning (o1 models)
    assistant_msg = AssistantMessage(
        "The answer is 42.",
        reasoning="I need to think about this carefully..."
    )
    print(f"With reasoning: {assistant_msg.reasoning}")

    # With citations
    # Note: CitationURL is expected, or str which gets converted
    assistant_msg = AssistantMessage(
        "According to recent research...",
        citations=["https://example.com/paper.pdf"]
    )
    print(f"With citations: {assistant_msg.citations}")

if __name__ == "__main__":
    asyncio.run(main())
