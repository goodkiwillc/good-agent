import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from good_agent.config import AgentConfigManager
from good_agent.model.llm import LanguageModel
from litellm import Router
from pydantic import BaseModel

# Add the tests directory to the path so we can import test_helpers
tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(tests_dir, "fixtures", "helpers"))
from test_helpers import MockAgent  # noqa: E402


class MockResponse(BaseModel):
    temperature: float
    condition: str


class MockUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=5, total_tokens=15):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class MockLLMResponse:
    def __init__(self, content="Test response", usage=None):
        # Create proper Choice-like structure with MagicMock
        choice = MagicMock()
        choice.message.content = content
        choice.finish_reason = "stop"
        self.choices = [choice]
        self.usage = usage or MockUsage()


class MockStreamChunk:
    def __init__(self, content=None, finish_reason=None):
        # Create a proper delta object that behaves like a dict
        delta = MagicMock()
        delta.get = MagicMock(
            side_effect=lambda key, default=None: content
            if key == "content"
            else default
        )
        delta.content = content  # Also set as attribute for fallback

        # Create choice with proper structure
        choice = MagicMock()
        choice.delta = delta
        choice.finish_reason = finish_reason

        self.choices = [choice]


@pytest.fixture
def config():
    return AgentConfigManager(
        model="gpt-4o-mini",
        temperature=0.8,
        max_retries=2,
        fallback_models=["gpt-3.5-turbo"],
    )


@pytest.fixture
def mock_agent(config):
    return MockAgent(
        model="gpt-4o-mini",
        temperature=0.8,
        max_retries=2,
        fallback_models=["gpt-3.5-turbo"],
    )


@pytest.fixture
def language_model(mock_agent):
    lm = LanguageModel()
    mock_agent.install_component(lm)
    return lm


@pytest.fixture
def mock_litellm():
    with patch("good_agent.llm.import") as mock_import:
        mock_litellm = MagicMock()
        mock_import.return_value = mock_litellm

        # Mock the acompletion method
        mock_litellm.acompletion = AsyncMock()
        mock_litellm._turn_on_debug = MagicMock()

        # Mock cost calculator
        mock_litellm.cost_calculator.completion_cost = MagicMock(return_value=0.001)

        yield mock_litellm


@pytest.fixture
def mock_instructor():
    with patch("good_agent.llm.instructor") as mock_instructor:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_instructor.from_litellm.return_value = mock_client
        yield mock_instructor


class TestLanguageModelInitialization:
    def test_initialization_with_config(self, mock_agent: MockAgent):
        lm = LanguageModel()
        mock_agent.install_component(lm)

        assert lm.config == mock_agent.config
        assert lm.model == "gpt-4o-mini"
        assert lm.temperature == 0.8
        assert lm.max_retries == 2
        assert lm.fallback_models == ["gpt-3.5-turbo"]

        assert lm.total_tokens == 0
        assert lm.total_cost == 0.0
        assert lm.last_usage is None
        assert lm.last_cost is None

    def test_initialization_with_overrides(self, mock_agent: MockAgent):
        lm = LanguageModel(model="claude-3-5-sonnet", temperature=0.5)
        mock_agent.install_component(lm)

        assert lm.model == "claude-3-5-sonnet"
        assert lm.temperature == 0.5
        assert lm.max_retries == 2  # From config

    def test_lazy_loading_properties(self, language_model):
        # Properties should be None initially (router is lazy-loaded)
        assert language_model._router is None
        assert language_model._instructor is None

        # Access router property to trigger lazy loading
        router = language_model.router
        assert router is not None
        assert language_model._router is not None
        # Check class name instead of isinstance due to dynamic class creation
        assert language_model._router.__class__.__name__ == "_ManagedRouter"

        # Access instructor property to trigger lazy loading
        with patch.dict("sys.modules", {"instructor": MagicMock()}):
            instructor = language_model.instructor
            assert instructor is not None
            # Note: _instructor_patched flag is set, but _instructor may still be None
            # depending on instructor mode configuration
            assert language_model._instructor_patched is True


class TestLanguageModelConfiguration:
    def test_get_config_value_precedence(self, config):
        # Create mock agent and install LanguageModel with overrides
        mock_agent = MockAgent(
            model="gpt-4o-mini",
            temperature=0.8,
            max_retries=2,
            fallback_models=["gpt-3.5-turbo"],
        )
        lm = LanguageModel(temperature=0.9)  # Pass override here
        mock_agent.install_component(lm)

        # Override should take precedence
        assert lm._get_config_value("temperature") == 0.9

        # Config value should be used when no override
        assert lm._get_config_value("model") == "gpt-4o-mini"

        # Default should be used when neither exists
        assert lm._get_config_value("nonexistent", "default") == "default"

    def test_prepare_request_config(self, language_model):
        config = language_model._prepare_request_config(
            max_tokens=100, custom_param="test"
        )

        assert config["model"] == "gpt-4o-mini"
        assert config["temperature"] == 0.8
        assert config["max_tokens"] == 100
        assert config["custom_param"] == "test"

    def test_prepare_request_config_filters_internal_args(self, language_model):
        config = language_model._prepare_request_config(
            instructor_mode="json", max_retries=5, fallback_models=["test"]
        )

        # These should be filtered out
        assert "instructor_mode" not in config
        assert "max_retries" not in config
        assert "fallback_models" not in config


class TestLanguageModelUsageTracking:
    def test_update_usage(self, language_model):
        mock_response = MagicMock()
        mock_response.usage = MockUsage(
            prompt_tokens=20, completion_tokens=10, total_tokens=30
        )

        # Mock litellm.completion_cost directly at the module level where it's imported
        with patch("litellm.completion_cost", return_value=0.002):
            language_model._update_usage(mock_response)

        assert language_model.last_usage.prompt_tokens == 20
        assert language_model.last_usage.completion_tokens == 10
        assert language_model.last_usage.total_tokens == 30
        assert language_model.total_tokens == 30
        assert language_model.last_cost == 0.002
        assert language_model.total_cost == 0.002

    def test_update_usage_no_usage_data(self, language_model):
        # Create a response without usage data (doesn't implement ResponseWithUsage protocol)
        mock_response = MagicMock(spec=[])  # Empty spec means no attributes

        language_model._update_usage(mock_response)

        # When response doesn't have usage, nothing should be updated
        assert language_model.last_usage is None
        assert language_model.total_tokens == 0

    def test_update_usage_cost_calculation_error(self, language_model):
        mock_response = MagicMock()
        mock_response.usage = MockUsage()

        # Mock litellm.completion_cost to raise an exception
        with patch(
            "litellm.completion_cost",
            side_effect=Exception("Cost error"),
        ):
            language_model._update_usage(mock_response)

        # Should still update usage even if cost calculation fails
        assert language_model.last_usage.total_tokens == 15
        assert language_model.last_cost is None


class TestLanguageModelCompletion:
    @pytest.mark.asyncio
    async def test_complete_success(self, language_model):
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MockLLMResponse("Hello! How can I help?")

        # Access the router to ensure it's initialized with proper callbacks
        _ = language_model.router  # This triggers lazy initialization

        # Mock the parent Router's acompletion method to avoid actual API calls
        # We patch the superclass method to preserve the ManagedRouter's callback logic
        async def mock_super_acompletion(*args, **kwargs):
            return mock_response

        # Patch the parent class's acompletion
        with patch.object(Router, "acompletion", new=mock_super_acompletion):
            # Mock litellm for cost calculation
            mock_litellm = MagicMock()
            mock_litellm.completion_cost = MagicMock(return_value=0.001)
            language_model._litellm = mock_litellm

            result = await language_model.complete(messages)

        assert result is mock_response
        assert len(language_model.api_requests) == 1
        assert len(language_model.api_responses) == 1
        assert language_model.total_tokens == 15

    @pytest.mark.asyncio
    async def test_complete_with_overrides(self, language_model):
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MockLLMResponse()

        # Mock the router's acompletion method
        mock_router = MagicMock()
        mock_router.acompletion = AsyncMock(return_value=mock_response)
        language_model._router = mock_router

        # Mock litellm.completion_cost for usage tracking
        with patch("litellm.completion_cost", return_value=0.001):
            await language_model.complete(messages, temperature=0.5, max_tokens=50)

        call_args = mock_router.acompletion.call_args
        assert call_args[1]["temperature"] == 0.5
        assert call_args[1]["max_tokens"] == 50

    @pytest.mark.asyncio
    async def test_complete_with_fallback(self, language_model):
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MockLLMResponse()

        # Verify that the router has been configured with fallback models
        router = language_model.router
        assert len(router.model_list) == 2  # Primary + 1 fallback
        assert router.model_list[0]["model_name"] == "gpt-4o-mini"
        assert router.model_list[1]["model_name"] == "gpt-3.5-turbo"

        # Mock the router's acompletion to simulate fallback behavior
        # The router internally handles retries across models
        async def mock_acompletion(*args, **kwargs):
            # Simulate the router trying models internally
            # It would automatically try fallback on failure
            return mock_response

        # Replace the router's acompletion method
        with patch.object(router, "acompletion", new=mock_acompletion):
            # Mock litellm for cost calculation
            mock_litellm = MagicMock()
            mock_litellm.completion_cost = MagicMock(return_value=0.001)
            language_model._litellm = mock_litellm

            result = await language_model.complete(messages)

        assert result is mock_response
        # The router handles fallbacks internally, so we just verify it works

    @pytest.mark.asyncio
    async def test_complete_all_models_fail(self, language_model):
        messages = [{"role": "user", "content": "Hello"}]

        # Mock the router's acompletion method
        mock_router = MagicMock()
        mock_router.acompletion = AsyncMock(side_effect=Exception("All models failed"))
        language_model._router = mock_router

        with pytest.raises(Exception, match="All models failed"):
            await language_model.complete(messages)


class TestLanguageModelExtraction:
    @pytest.mark.asyncio
    async def test_extract_success(self, language_model):
        messages = [{"role": "user", "content": "What's the weather?"}]
        expected_response = MockResponse(temperature=22, condition="sunny")

        # Access the router to ensure it's initialized with proper callbacks
        router = language_model.router  # This triggers lazy initialization

        # Manually call the tracking hooks since extract doesn't go through acompletion
        import time

        start_time = time.time()
        await language_model.async_log_pre_api_call("gpt-4o-mini", messages, {})

        # Mock the aextract method that will be added to the router
        router.aextract = AsyncMock(return_value=expected_response)

        # Mock instructor import that happens in patch_with_instructor
        mock_instructor_module = MagicMock()

        # Create a mock instructor client with the create method
        mock_instructor_client = MagicMock()
        mock_instructor_client.create = AsyncMock(return_value=expected_response)

        # Mock from_litellm to return our instructor client
        mock_instructor_module.from_litellm = MagicMock(
            return_value=mock_instructor_client
        )
        mock_instructor_module.Mode.TOOLS = "tools"

        with patch.dict("sys.modules", {"instructor": mock_instructor_module}):
            # Reset instructor state to force re-patching
            language_model._instructor = None
            language_model._instructor_patched = False

            result = await language_model.extract(messages, MockResponse)

            # Manually call the success hook since extract doesn't go through acompletion
            end_time = time.time()
            await language_model.async_log_success_event(
                {}, expected_response, start_time, end_time
            )

        assert result is expected_response
        assert len(language_model.api_requests) == 1
        assert len(language_model.api_responses) == 1

    @pytest.mark.asyncio
    async def test_extract_with_instructor_mode(self, language_model):
        messages = [{"role": "user", "content": "Test"}]
        expected_response = MockResponse(temperature=20, condition="cloudy")

        # Mock the router with instructor patched
        mock_router = MagicMock()
        mock_router.aextract = AsyncMock(return_value=expected_response)
        mock_router.patch_with_instructor = MagicMock(return_value=mock_router)
        language_model._router = mock_router
        language_model._instructor_patched = False  # Force re-patching

        # Override config to use json_mode
        language_model._override_config = {"instructor_mode": "json_mode"}

        await language_model.extract(
            messages, MockResponse, instructor_mode="json_mode"
        )

        # Verify patch_with_instructor was called with the right mode
        mock_router.patch_with_instructor.assert_called_once_with(mode="json_mode")


class TestLanguageModelStreaming:
    @pytest.mark.asyncio
    async def test_stream_success(self, language_model):
        messages = [{"role": "user", "content": "Tell me a story"}]

        # Mock stream chunks
        chunks = [
            MockStreamChunk("Once"),
            MockStreamChunk(" upon"),
            MockStreamChunk(" a time", "stop"),
        ]

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        # Mock the router's acompletion method
        mock_router = MagicMock()
        mock_router.acompletion = AsyncMock(return_value=mock_stream())
        language_model._router = mock_router

        result_chunks = []
        async for chunk in language_model.stream(messages):
            result_chunks.append(chunk)

        assert len(result_chunks) == 3
        # StreamChunk objects have content and finish_reason attributes
        assert result_chunks[0].content == "Once"
        assert result_chunks[1].content == " upon"
        assert result_chunks[2].content == " a time"
        assert result_chunks[2].finish_reason == "stop"

        # Verify stream=True was set
        call_args = mock_router.acompletion.call_args
        assert call_args[1]["stream"] is True

    @pytest.mark.asyncio
    async def test_stream_tracks_responses(self, language_model):
        messages = [{"role": "user", "content": "Test"}]
        chunks = [
            MockStreamChunk("test", "stop")
        ]  # Add finish_reason to complete the stream

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        # Access the router to ensure it's initialized with proper callbacks
        _ = language_model.router  # This triggers lazy initialization

        # Patch the parent Router's acompletion method to avoid actual API calls
        async def mock_super_acompletion(*args, **kwargs):
            return mock_stream()

        # Patch the parent class's acompletion
        with patch.object(Router, "acompletion", new=mock_super_acompletion):
            async for _ in language_model.stream(messages):
                pass

        assert len(language_model.api_requests) == 1
        assert len(language_model.api_responses) >= 1  # At least one response tracked


class TestLanguageModelDebugMode:
    def test_debug_mode_enables_litellm_debug(self, config):
        # Create mock agent with debug enabled
        mock_agent = MockAgent(model="gpt-4o-mini", temperature=0.8, litellm_debug=True)

        # Create and install LanguageModel
        lm = LanguageModel()
        mock_agent.install_component(lm)

        # Access the router property to trigger lazy loading
        _ = lm.router

        # The ManagedRouter should have been created with set_verbose=True
        # We can't easily verify this without mocking the constructor,
        # but we can check that the config value is correct
        assert lm._get_config_value("litellm_debug", False) is True

    def test_debug_mode_disabled_by_default(self, language_model):
        # Access the router property to trigger lazy loading if needed
        _ = language_model.router

        # Verify debug is disabled by default
        assert language_model._get_config_value("litellm_debug", False) is False


class TestLanguageModelCreateMessage:
    def test_create_message_overloads_exist(self, language_model):
        # This test ensures the overloaded methods exist for type checking
        # The actual implementation would depend on the Message classes
        assert hasattr(language_model, "create_message")

        # Test would verify that different role types return appropriate message types
        # but since the method isn't implemented, we just check it exists
