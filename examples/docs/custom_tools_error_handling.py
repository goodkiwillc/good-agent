"""Error handling patterns in custom tools."""

import asyncio

from good_agent import Agent, tool


@tool
async def divide_numbers(a: float, b: float) -> float:
    """
    Divide two numbers with error handling.

    Args:
        a: Numerator
        b: Denominator

    Returns:
        Result of a / b

    Raises:
        ValueError: If denominator is zero
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")

    return a / b


@tool
async def safe_divide(a: float, b: float) -> dict:
    """
    Divide with graceful error handling.

    Returns error information instead of raising exceptions.
    """
    if b == 0:
        return {
            "success": False,
            "error": "Cannot divide by zero",
            "suggestion": "Please provide a non-zero denominator",
        }

    return {"success": True, "result": a / b}


async def main():
    """Demonstrate error handling patterns."""
    async with Agent("Math assistant", tools=[divide_numbers, safe_divide]) as agent:
        # Test divide_numbers (raises exception)
        try:
            result = await agent.invoke(divide_numbers, a=10, b=2)
            print(f"Division result: {result.response}")

            # This will raise an error
            result = await agent.invoke(divide_numbers, a=10, b=0)
        except Exception:
            print("divide_numbers raised an error for zero denominator")

        # Test safe_divide (returns error dict)
        result = await agent.invoke(safe_divide, a=10, b=0)
        print(f"Safe divide result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
