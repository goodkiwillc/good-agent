import json

import pytest
from good_agent import Agent
from good_agent.messages import ToolCall
from good_agent.tools import ToolCallFunction, tool

# Mark all tests as expected to fail until invoke is implemented
# pytestmark = pytest.mark.xfail(reason="invoke functionality not yet implemented")


class TestInvokeIntegration:
    """Integration tests for invoke functionality"""

    @pytest.mark.asyncio
    async def test_invoke_in_conversation_flow(self):
        """Test invoke within a real conversation flow"""

        @tool
        async def get_weather(location: str) -> str:
            """Get weather for a location"""
            # Simulate API call
            return f"The weather in {location} is sunny, 72°F"

        @tool
        async def get_time(timezone: str) -> str:
            """Get time in a timezone"""
            # Simulate API call
            return f"The current time in {timezone} is 3:45 PM"

        async with Agent(
            "You are a helpful assistant.",
            model="gpt-5-mini",
            tools=[get_weather, get_time],
        ) as agent:
            # Scenario 1: Direct tool invocation (programmatic)
            # User asks a question
            agent.append("What's the weather like in Paris?")

            # Directly invoke tool - this creates assistant message AND tool response
            weather_result = await agent.tool_calls.invoke(get_weather, location="Paris")

            assert weather_result.success is True
            assert "Paris" in weather_result.response
            assert "sunny" in weather_result.response

            # Verify invoke created the assistant message with tool call
            assert agent[-2].role == "assistant"
            assert len(agent[-2].tool_calls) == 1
            assert agent[-2].tool_calls[0].function.name == "get_weather"

            # And the tool response
            assert agent[-1].role == "tool"
            assert agent[-1].content == weather_result.response

            # Now add a final assistant response
            agent.assistant.append(
                "The weather in Paris is currently sunny with a temperature of 72°F. ",
                "Would you like to know anything else?",
            )

            # Scenario 2: Processing LLM tool calls
            # User asks follow-up
            agent.append("What time is it there?")

            # Simulate LLM response with tool call
            agent.assistant.append(
                "I'll check the current time in Paris for you.",
                tool_calls=[
                    ToolCall(
                        id="llm_call_456",
                        type="function",
                        function=ToolCallFunction(
                            name="get_time",
                            arguments=json.dumps({"timezone": "Europe/Paris"}),
                        ),
                    )
                ],
            )

            # Process the LLM's tool call - skip assistant message since it exists
            time_result = await agent.tool_calls.invoke(
                get_time,
                tool_call_id="llm_call_456",
                skip_assistant_message=True,
                timezone="Europe/Paris",
            )

            assert time_result.success is True
            assert "3:45 PM" in time_result.response
            assert agent[-1].tool_call_id == "llm_call_456"

    @pytest.mark.asyncio
    async def test_invoke_many_for_parallel_data_gathering(self):
        """Test invoke_many for gathering data from multiple sources"""

        @tool
        async def fetch_stock_price(symbol: str) -> float:
            """Fetch current stock price"""
            # Simulate API call
            prices = {"AAPL": 195.83, "GOOGL": 178.21, "MSFT": 425.92}
            return prices.get(symbol, 0.0)

        @tool
        async def fetch_company_news(symbol: str) -> list[str]:
            """Fetch latest company news"""
            # Simulate API call
            news = {
                "AAPL": ["Apple announces new AI features", "iPhone sales up 15%"],
                "GOOGL": ["Google Cloud revenue grows", "New Gemini model released"],
                "MSFT": ["Microsoft Teams adds features", "Azure growth continues"],
            }
            return news.get(symbol, [])

        async with Agent(
            "You are a financial assistant.",
            model="gpt-5-mini",
            tools=[fetch_stock_price, fetch_company_news],
        ) as agent:
            # User wants portfolio update
            agent.append("Give me an update on my portfolio: AAPL, GOOGL, and MSFT")

            # Gather all data in parallel
            results = await agent.tool_calls.invoke_many(
                [
                    (fetch_stock_price, {"symbol": "AAPL"}),
                    (fetch_stock_price, {"symbol": "GOOGL"}),
                    (fetch_stock_price, {"symbol": "MSFT"}),
                    (fetch_company_news, {"symbol": "AAPL"}),
                    (fetch_company_news, {"symbol": "GOOGL"}),
                    (fetch_company_news, {"symbol": "MSFT"}),
                ]
            )

            # Verify all results - results is a list of ToolResponse objects
            assert len(results) == 6
            assert all(result.success for result in results)

            # Should have prices for all stocks
            prices_collected = [
                msg
                for msg in agent.messages
                if msg.role == "tool" and "fetch_stock_price" in msg.tool_name
            ]
            assert len(prices_collected) >= 3

    @pytest.mark.asyncio
    async def test_invoke_func_for_repeated_operations(self):
        """Test invoke_func for creating reusable tool invocations"""

        @tool
        async def translate(text: str, from_lang: str, to_lang: str) -> str:
            """Translate text between languages"""
            # Simulate translation
            if to_lang == "es":
                translations = {
                    "Hello": "Hola",
                    "Goodbye": "Adiós",
                    "Thank you": "Gracias",
                }
                return translations.get(text, f"[{text} in Spanish]")
            return f"[{text} in {to_lang}]"

        async with Agent(
            "You are a translation assistant.",
            model="gpt-5-mini",
            tools=[translate],
        ) as agent:
            # Create a bound function for English to Spanish translation
            to_spanish = agent.tool_calls.invoke_func(translate, from_lang="en", to_lang="es")

            # Use it multiple times
            greetings = ["Hello", "Goodbye", "Thank you"]
            for greeting in greetings:
                result = await to_spanish(text=greeting)
                assert result.success is True
                assert result.response != greeting  # Should be translated

            # Verify message history shows all translations
            tool_messages = [msg for msg in agent if msg.role == "tool"]
            assert len(tool_messages) == 3

    @pytest.mark.asyncio
    async def test_resolve_pending_tool_calls_integration(self):
        """Test resolving tool calls from LLM responses"""

        @tool
        async def search_web(query: str) -> str:
            """Search the web for information"""
            return f"Found 10 results for '{query}'"

        @tool
        async def summarize(text: str, max_words: int = 100) -> str:
            """Summarize text"""
            words = text.split()[:max_words]
            return " ".join(words) + "..."

        async with Agent(
            "You are a research assistant.",
            model="gpt-5-mini",
            tools=[search_web, summarize],
        ) as agent:
            # User asks complex question
            agent.append(
                "Search for information about quantum computing and summarize it"
            )

            # Simulate LLM response with multiple tool calls
            agent.assistant.append(
                "I'll search for quantum computing information and provide a summary.",
                tool_calls=[
                    ToolCall(
                        id="search_001",
                        type="function",
                        function=ToolCallFunction(
                            name="search_web",
                            arguments=json.dumps({"query": "quantum computing basics"}),
                        ),
                    ),
                    ToolCall(
                        id="search_002",
                        type="function",
                        function=ToolCallFunction(
                            name="search_web",
                            arguments=json.dumps(
                                {"query": "quantum computing applications"}
                            ),
                        ),
                    ),
                ],
            )

            # Check pending calls
            pending = agent.tool_calls.get_pending_tool_calls()
            assert len(pending) == 2
            assert pending[0].id == "search_001"
            assert pending[1].id == "search_002"

            tool_messages = []
            async for tool_message in agent.tool_calls.resolve_pending_tool_calls():
                tool_messages.append(tool_message)

            # Verify all calls were resolved
            assert agent.tool_calls.has_pending_tool_calls() is False
            assert len(tool_messages) == 2

            assert sorted([msg.tool_call_id for msg in tool_messages]) == [
                "search_001",
                "search_002",
            ]

    @pytest.mark.asyncio
    async def test_invoke_with_custom_tool_response(self):
        """Test tools that return custom ToolResponse objects"""
        from good_agent.tools import ToolResponse

        @tool
        async def validate_email(email: str) -> ToolResponse:
            """Validate an email address"""
            import re

            pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            is_valid = bool(re.match(pattern, email))

            if is_valid:
                return ToolResponse(
                    tool_name="validate_email",
                    tool_call_id="",
                    response={
                        "email": email,
                        "valid": True,
                        "domain": email.split("@")[1],
                    },
                    parameters={"email": email},
                    success=True,
                    error=None,
                )
            else:
                return ToolResponse(
                    tool_name="validate_email",
                    tool_call_id="",
                    response=None,
                    parameters={"email": email},
                    success=False,
                    error=f"Invalid email format: {email}",
                )

        async with Agent(
            "You are an email validation assistant.",
            model="gpt-5-mini",
            tools=[validate_email],
        ) as agent:
            # Test valid email
            valid_result = await agent.tool_calls.invoke(validate_email, email="user@example.com")
            assert valid_result.success is True
            assert valid_result.response["valid"] is True
            assert valid_result.response["domain"] == "example.com"

            # Test invalid email
            invalid_result = await agent.tool_calls.invoke(validate_email, email="not-an-email")
            assert invalid_result.success is False
            assert "Invalid email format" in invalid_result.error

    @pytest.mark.asyncio
    async def test_invoke_many_func_for_batch_processing(self):
        """Test invoke_many_func for batch processing scenarios"""

        @tool
        async def process_image(url: str, operation: str) -> dict:
            """Process an image with specified operation"""
            # Simulate image processing
            return {
                "url": url,
                "operation": operation,
                "status": "completed",
                "dimensions": "1920x1080",
            }

        @tool
        async def upload_to_cdn(local_path: str, cdn_path: str) -> str:
            """Upload file to CDN"""
            # Simulate upload
            return f"https://cdn.example.com{cdn_path}"

        async with Agent(
            "You are an image processing assistant.",
            model="gpt-5-mini",
            tools=[process_image, upload_to_cdn],
        ) as agent:
            # Create a batch processing function
            batch_processor = agent.tool_calls.invoke_many_func(
                [
                    (
                        process_image,
                        {
                            "url": "https://example.com/image1.jpg",
                            "operation": "resize",
                        },
                    ),
                    (
                        process_image,
                        {
                            "url": "https://example.com/image2.jpg",
                            "operation": "crop",
                        },
                    ),
                    (
                        upload_to_cdn,
                        {
                            "local_path": "/tmp/processed1.jpg",
                            "cdn_path": "/images/processed1.jpg",
                        },
                    ),
                ]
            )

            # Execute batch operation
            results = await batch_processor()

            # Verify all operations completed - results is a list of ToolResponse objects
            assert all(result.success for result in results)

            # Can execute the same batch again
            results2 = await batch_processor()
            assert len(results2) == len(results)
