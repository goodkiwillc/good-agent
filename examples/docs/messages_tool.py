import asyncio
from good_agent.messages import ToolMessage
from good_agent.tools import ToolResponse

async def main():
    # Basic tool result
    tool_msg = ToolMessage(
        content="Result: 42",
        tool_call_id="call_123",
        tool_name="calculator"
    )
    print(f"Basic tool msg: {tool_msg.content}")

    # With structured response
    calculator_result = ToolResponse(
        tool_name="calculator",
        tool_call_id="call_123",
        response={"result": 42},
        success=True,
        parameters={}
    )
    
    tool_msg = ToolMessage(
        content="Calculation complete",
        tool_call_id="call_123", 
        tool_name="calculator",
        tool_response=calculator_result  # ToolResponse object
    )
    print(f"Structured tool msg: {tool_msg.tool_response}")

if __name__ == "__main__":
    asyncio.run(main())
