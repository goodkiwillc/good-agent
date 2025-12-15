import pytest
from pydantic import BaseModel

from good_agent.mock import (
    MockLanguageModel,
    create_failing_mock_llm,
    create_mock_language_model,
    create_streaming_mock_llm,
    create_successful_mock_llm,
)


class MockResponse(BaseModel):
    answer: str = "default answer"
    confidence: float = 0.9


class TestMockLanguageModel:
    """Test the MockLanguageModel functionality"""

    def test_mock_llm_initialization(self):
        mock_llm = MockLanguageModel({})

        assert mock_llm.model == "mock-model"
        assert mock_llm.temperature == 0.7
        assert mock_llm.complete_calls == []
        assert mock_llm.extract_calls == []
        assert mock_llm.stream_calls == []

    @pytest.mark.asyncio
    async def test_mock_complete_default_response(self):
        mock_llm = MockLanguageModel({})
        messages = [{"role": "user", "content": "Hello"}]

        result = await mock_llm.complete(messages)

        # Should have default mock response
        assert result.choices[0].message.content == "Mock response"
        assert mock_llm.total_tokens == 15

        # Should track the call
        assert len(mock_llm.complete_calls) == 1
        assert mock_llm.complete_calls[0]["messages"] == messages

    @pytest.mark.asyncio
    async def test_mock_complete_custom_response(self):
        mock_llm = MockLanguageModel({})

        # Set custom response
        from unittest.mock import MagicMock

        custom_response = MagicMock()
        custom_response.choices = [MagicMock()]
        custom_response.choices[0].message.content = "Custom response"
        mock_llm.set_complete_response(custom_response)

        messages = [{"role": "user", "content": "Hello"}]
        result = await mock_llm.complete(messages)

        assert result is custom_response

    @pytest.mark.asyncio
    async def test_mock_extract_default_response(self):
        mock_llm = MockLanguageModel({})
        messages = [{"role": "user", "content": "Test"}]

        result = await mock_llm.extract(messages, MockResponse)

        # Should create default instance
        assert isinstance(result, MockResponse)
        assert result.answer == "default answer"
        assert result.confidence == 0.9

        # Should track the call
        assert len(mock_llm.extract_calls) == 1
        assert mock_llm.extract_calls[0]["response_model"] is MockResponse

    @pytest.mark.asyncio
    async def test_mock_extract_custom_response(self):
        mock_llm = MockLanguageModel({})

        # Set custom response
        custom_response = MockResponse(answer="custom", confidence=0.95)
        mock_llm.set_extract_response(custom_response)

        messages = [{"role": "user", "content": "Test"}]
        result = await mock_llm.extract(messages, MockResponse)

        assert result is custom_response
        assert result.answer == "custom"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_mock_stream_default_chunks(self):
        mock_llm = MockLanguageModel({})
        messages = [{"role": "user", "content": "Stream test"}]

        chunks = []
        async for chunk in mock_llm.stream(messages):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0].content == "Mock "
        assert chunks[1].content == "stream "
        assert chunks[2].content == "response"
        assert chunks[2].finish_reason == "stop"

        # Should track the call
        assert len(mock_llm.stream_calls) == 1

    @pytest.mark.asyncio
    async def test_mock_stream_custom_chunks(self):
        mock_llm = MockLanguageModel({})

        # Set custom chunks
        mock_llm.set_stream_chunks(["Hello", " ", "world!"])

        messages = [{"role": "user", "content": "Stream test"}]

        chunks = []
        async for chunk in mock_llm.stream(messages):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " "
        assert chunks[2].content == "world!"

    @pytest.mark.asyncio
    async def test_mock_failure_mode(self):
        mock_llm = MockLanguageModel({})
        mock_llm.set_failure(True, "Test failure")

        messages = [{"role": "user", "content": "Test"}]

        # All methods should fail
        with pytest.raises(Exception, match="Test failure"):
            await mock_llm.complete(messages)

        with pytest.raises(Exception, match="Test failure"):
            await mock_llm.extract(messages, MockResponse)

        with pytest.raises(Exception, match="Test failure"):
            async for _ in mock_llm.stream(messages):
                pass

    def test_call_tracking_and_reset(self):
        mock_llm = MockLanguageModel({})

        # Make some calls to populate tracking
        mock_llm.complete_calls.append({"test": "data"})
        mock_llm.extract_calls.append({"test": "data"})
        mock_llm.stream_calls.append({"test": "data"})

        assert len(mock_llm.complete_calls) == 1
        assert len(mock_llm.extract_calls) == 1
        assert len(mock_llm.stream_calls) == 1

        # Reset should clear all calls
        mock_llm.reset_calls()

        assert len(mock_llm.complete_calls) == 0
        assert len(mock_llm.extract_calls) == 0
        assert len(mock_llm.stream_calls) == 0


class TestMockLLMFactoryFunctions:
    """Test the factory functions for creating mock LLMs"""

    def test_create_successful_mock_llm(self):
        mock_llm = create_successful_mock_llm()

        assert mock_llm.model == "mock-model"
        assert not mock_llm.should_fail

    def test_create_failing_mock_llm(self):
        mock_llm = create_failing_mock_llm("Custom failure")

        assert mock_llm.should_fail
        assert mock_llm.failure_message == "Custom failure"

    def test_create_streaming_mock_llm(self):
        chunks = ["Hello", " world", "!"]
        mock_llm = create_streaming_mock_llm(chunks)

        assert len(mock_llm.mock_stream_chunks) == 3
        assert mock_llm.mock_stream_chunks[0].content == "Hello"
        assert mock_llm.mock_stream_chunks[1].content == " world"
        assert mock_llm.mock_stream_chunks[2].content == "!"

    def test_create_mock_language_model_with_all_options(self):
        from unittest.mock import MagicMock

        custom_complete = MagicMock()
        custom_extract = MockResponse(answer="test", confidence=0.8)
        custom_chunks = ["chunk1", "chunk2"]

        mock_llm = create_mock_language_model(
            complete_response=custom_complete,
            extract_response=custom_extract,
            stream_chunks=custom_chunks,
            should_fail=False,
            config={"model": "custom-model", "temperature": 0.5},
        )

        assert mock_llm.model == "custom-model"
        assert mock_llm.temperature == 0.5
        assert mock_llm.mock_complete_response is custom_complete
        assert mock_llm.mock_extract_response is custom_extract
        assert len(mock_llm.mock_stream_chunks) == 2
        assert not mock_llm.should_fail
