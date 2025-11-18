from unittest.mock import AsyncMock, MagicMock

import pytest
from litellm.types.completion import ChatCompletionMessageParam
from good_agent.model.llm import LanguageModel, StreamChunk


class MockStreamChoice:
    """Mock streaming choice object."""

    def __init__(self, content=None, finish_reason=None):
        self.delta = MagicMock()
        self.delta.content = content
        self.delta.get = MagicMock(return_value=content)
        self.finish_reason = finish_reason
        self.index = 0  # litellm expects this

    def __getitem__(self, key):
        """Make object subscriptable like litellm choices."""
        return getattr(self, key)

    def get(self, key, default=None):
        """Support .get() method like litellm choices."""
        return getattr(self, key, default)


class MockHiddenParams:
    """Mock HiddenParams object matching litellm's structure."""

    def __init__(self):
        self.created_at = None
        self.model_id = None
        self.api_base = None

    def get(self, key, default=None):
        return getattr(self, key, default)


class MockStreamResponse:
    """Mock streaming response object that matches litellm's ModelResponseStream structure."""

    def __init__(self, content=None, finish_reason=None):
        self.choices = [MockStreamChoice(content, finish_reason)]
        # Add _hidden_params to match litellm's expected structure
        self._hidden_params = MockHiddenParams()
        # Add common litellm response attributes
        self.id = "chatcmpl-mock"
        self.object = "chat.completion.chunk"
        self.created = 1234567890
        self.model = "gpt-4o-mini"

    def __getitem__(self, key):
        """Make object subscriptable like litellm responses."""
        return getattr(self, key)

    def get(self, key, default=None):
        """Support .get() method like litellm responses."""
        return getattr(self, key, default)


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    import os
    import sys

    # Add the tests directory to the path so we can import test_helpers
    tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, os.path.join(tests_dir, "fixtures", "helpers"))
    from test_helpers import MockAgent  # type: ignore[import-not-found]

    return MockAgent(model="gpt-4o-mini", temperature=0.5)


@pytest.fixture
def language_model(mock_agent):
    """Create a language model with mock agent."""
    lm = LanguageModel(model="gpt-4o-mini", temperature=0.5)
    mock_agent.install_component(lm)
    return lm


@pytest.mark.asyncio
async def test_stream_yields_chunks(language_model):
    """Test that stream method yields StreamChunk objects."""

    # Mock the stream response
    async def mock_stream():
        chunks = [
            MockStreamResponse("Hello"),
            MockStreamResponse(" world"),
            MockStreamResponse("!", "stop"),
        ]
        for chunk in chunks:
            yield chunk

    # Directly set the _router with our mock
    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    language_model._router = mock_router

    messages = [{"role": "user", "content": "Test"}]
    chunks_received = []

    async for chunk in language_model.stream(messages):
        chunks_received.append(chunk)

    # Verify we got the right number of chunks
    assert len(chunks_received) == 3

    # Verify chunk types and content
    assert all(isinstance(chunk, StreamChunk) for chunk in chunks_received)
    assert chunks_received[0].content == "Hello"
    assert chunks_received[1].content == " world"
    assert chunks_received[2].content == "!"
    assert chunks_received[2].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_tracks_responses(language_model):
    """Test that streaming tracks responses in api_stream_responses."""

    async def mock_stream():
        chunks = [
            MockStreamResponse("Test"),
            MockStreamResponse(" response"),
        ]
        for chunk in chunks:
            yield chunk

    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    language_model._router = mock_router

    messages = [{"role": "user", "content": "Test"}]
    chunks_received = []

    async for chunk in language_model.stream(messages):
        chunks_received.append(chunk)

    # Verify chunks were tracked
    assert len(language_model.api_stream_responses) == 2
    assert language_model.api_stream_responses[0].content == "Test"
    assert language_model.api_stream_responses[1].content == " response"


@pytest.mark.asyncio
async def test_stream_handles_empty_chunks(language_model):
    """Test that stream handles chunks with no content gracefully."""

    async def mock_stream():
        chunks = [
            MockStreamResponse("Start"),
            MockStreamResponse(None),  # Empty chunk
            MockStreamResponse("End", "stop"),
        ]
        for chunk in chunks:
            yield chunk

    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    language_model._router = mock_router

    messages = [{"role": "user", "content": "Test"}]
    chunks_received = []

    async for chunk in language_model.stream(messages):
        chunks_received.append(chunk)

    # All chunks should be yielded, even empty ones
    assert len(chunks_received) == 3
    assert chunks_received[0].content == "Start"
    assert chunks_received[1].content is None
    assert chunks_received[2].content == "End"


@pytest.mark.asyncio
async def test_stream_with_error_handling(language_model):
    """Test that stream handles errors properly."""

    async def mock_stream():
        yield MockStreamResponse("Start")
        raise Exception("Stream error")

    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    language_model._router = mock_router

    messages = [{"role": "user", "content": "Test"}]

    with pytest.raises(Exception, match="Stream error"):
        async for _ in language_model.stream(messages):
            pass

    # Error should be tracked
    assert len(language_model.api_errors) > 0


@pytest.mark.asyncio
async def test_stream_passes_correct_params(language_model):
    """Test that stream passes correct parameters to the router."""

    async def mock_stream():
        yield MockStreamResponse("Test", "stop")

    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    language_model._router = mock_router

    messages = [{"role": "user", "content": "Test"}]
    await language_model.stream(messages, max_tokens=100).__anext__()

    # Verify acompletion was called with stream=True
    call_args = mock_router.acompletion.call_args
    assert call_args[1]["stream"] is True
    assert call_args[1]["max_tokens"] == 100
    assert call_args[1]["temperature"] == 0.5  # From fixture


@pytest.mark.asyncio
async def test_stream_with_reasoning_content():
    """Test streaming with reasoning content (for models that support it)."""
    # This tests the more advanced streaming interface similar to Thread library

    class MockStreamChoiceWithReasoning:
        def __init__(self, content=None, reasoning=None, finish_reason=None):
            self.delta = MagicMock()
            self.delta.content = content
            self.delta.reasoning_content = reasoning

            def delta_get(key, default=None):
                if key == "content":
                    return content
                elif key == "reasoning_content":
                    return reasoning
                elif key == "thinking_blocks":
                    return [{"thinking": reasoning}] if reasoning else None
                return default

            self.delta.get = delta_get
            self.finish_reason = finish_reason
            self.index = 0  # litellm expects this

        def __getitem__(self, key):
            """Make object subscriptable like litellm choices."""
            return getattr(self, key)

        def get(self, key, default=None):
            """Support .get() method like litellm choices."""
            return getattr(self, key, default)

    class MockStreamResponseWithReasoning:
        def __init__(self, content=None, reasoning=None, finish_reason=None):
            self.choices = [
                MockStreamChoiceWithReasoning(content, reasoning, finish_reason)
            ]
            # Add _hidden_params to match litellm's expected structure
            self._hidden_params = MockHiddenParams()
            # Add common litellm response attributes
            self.id = "chatcmpl-mock-reasoning"
            self.object = "chat.completion.chunk"
            self.created = 1234567890
            self.model = "gpt-4o-mini"

        def __getitem__(self, key):
            """Make object subscriptable like litellm responses."""
            return getattr(self, key)

        def get(self, key, default=None):
            """Support .get() method like litellm responses."""
            return getattr(self, key, default)

    import os
    import sys

    # Add parent directory to path to import test_helpers
    tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, os.path.join(tests_dir, "fixtures", "helpers"))
    from test_helpers import MockAgent  # type: ignore[import-not-found]

    mock_agent = MockAgent(model="gpt-4o-mini")
    lm = LanguageModel(model="gpt-4o-mini")
    mock_agent.install_component(lm)

    async def mock_stream():
        chunks = [
            MockStreamResponseWithReasoning(reasoning="Let me think..."),
            MockStreamResponseWithReasoning(reasoning=" about this problem."),
            MockStreamResponseWithReasoning(content="The answer"),
            MockStreamResponseWithReasoning(content=" is 42.", finish_reason="stop"),
        ]
        for chunk in chunks:
            yield chunk

    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    lm._router = mock_router

    messages: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": "What is the meaning of life?"}
    ]
    chunks_received = []

    async for chunk in lm.stream(messages):
        chunks_received.append(chunk)

    # We should get all chunks
    assert len(chunks_received) == 4

    # First two chunks have no content (reasoning only)
    assert chunks_received[0].content is None
    assert chunks_received[1].content is None

    # Last two chunks have content
    assert chunks_received[2].content == "The answer"
    assert chunks_received[3].content == " is 42."
    assert chunks_received[3].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_wrapper_interface():
    """Test implementing a StreamingMessageWrapper similar to Thread library."""

    class StreamingWrapper:
        """Wrapper to collect streaming chunks similar to Thread's StreamingMessageWrapper."""

        def __init__(self, language_model, messages, **kwargs):
            self.lm = language_model
            self.messages = messages
            self.kwargs = kwargs
            self.content = ""
            self.reasoning = ""
            self.chunks = []
            self._complete = False

        @property
        async def stream(self):
            """Stream and collect chunks."""
            try:
                async for chunk in self.lm.stream(self.messages, **self.kwargs):
                    self.chunks.append(chunk)
                    if chunk.content:
                        self.content += chunk.content
                    # Note: Current StreamChunk doesn't have reasoning,
                    # but this shows how it could be extended
                    yield chunk
            finally:
                self._complete = True

        async def complete(self):
            """Get the complete message after streaming."""
            if not self._complete:
                raise ValueError("Stream not complete")
            return self.content

    # Test the wrapper
    import os
    import sys

    # Add parent directory to path to import test_helpers
    tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, os.path.join(tests_dir, "fixtures", "helpers"))
    from test_helpers import MockAgent  # type: ignore[import-not-found]

    mock_agent = MockAgent(model="gpt-4o-mini")
    lm = LanguageModel(model="gpt-4o-mini")
    mock_agent.install_component(lm)

    async def mock_stream():
        for word in ["Hello", " ", "world", "!"]:
            yield MockStreamResponse(word)
        yield MockStreamResponse(None, "stop")

    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    lm._router = mock_router

    messages: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": "Test"}
    ]
    wrapper = StreamingWrapper(lm, messages)

    # Stream and collect
    chunks = []
    async for chunk in wrapper.stream:
        chunks.append(chunk)

    # Verify streaming worked
    assert len(chunks) == 5
    assert wrapper._complete is True

    # Get complete content
    complete_content = await wrapper.complete()
    assert complete_content == "Hello world!"


@pytest.mark.asyncio
async def test_stream_integration_with_agent():
    """Test streaming through the Agent interface."""
    import os
    import sys

    # Add parent directory to path to import test_helpers
    tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, os.path.join(tests_dir, "fixtures", "helpers"))
    from test_helpers import MockAgent  # type: ignore[import-not-found]

    mock_agent = MockAgent(model="gpt-4o-mini", temperature=0.7)
    lm = LanguageModel(model="gpt-4o-mini", temperature=0.7)
    mock_agent.install_component(lm)

    # Mock the stream at the language model level
    async def mock_stream():
        for word in ["I", " am", " ready", " to", " help", "."]:
            yield MockStreamResponse(word)
        yield MockStreamResponse(None, "stop")

    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(return_value=mock_stream())
    lm._router = mock_router

    messages: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": "Are you ready?"}
    ]

    # Stream through language model
    chunks = []
    async for chunk in lm.stream(messages):
        chunks.append(chunk)

    # Verify we got all chunks
    assert len(chunks) == 7  # 6 words + 1 stop

    # Reconstruct message
    full_message = "".join(c.content or "" for c in chunks)
    assert full_message == "I am ready to help."
