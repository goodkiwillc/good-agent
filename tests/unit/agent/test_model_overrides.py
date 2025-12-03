import pytest
from good_agent.model.overrides import (
    ModelOverride,
    ModelOverrideRegistry,
    ParameterOverride,
)


class TestParameterOverride:
    def test_drop_action(self):
        override = ParameterOverride(action="drop")
        should_include, value = override.apply(0.7)
        assert not should_include
        assert value is None

    def test_override_action(self):
        override = ParameterOverride(action="override", value=1.0)
        should_include, value = override.apply(0.7)
        assert should_include
        assert value == 1.0

    def test_transform_action(self):
        override = ParameterOverride(action="transform", transform=lambda x: x * 2)
        should_include, value = override.apply(5)
        assert should_include
        assert value == 10

    def test_unknown_action(self):
        override = ParameterOverride(action="unknown")
        should_include, value = override.apply("test")
        assert should_include
        assert value == "test"


class TestModelOverride:
    def test_exact_match(self):
        override = ModelOverride(model_pattern="gpt-4")
        assert override.matches("gpt-4")
        assert not override.matches("gpt-4o")
        assert not override.matches("gpt-3.5-turbo")

    def test_wildcard_match(self):
        override = ModelOverride(model_pattern="gpt-5*")
        assert override.matches("gpt-5")
        assert override.matches("gpt-5-mini")
        assert override.matches("gpt-5-turbo")
        assert not override.matches("gpt-4")

    def test_apply_to_config_with_drops(self):
        override = ModelOverride(
            model_pattern="test-model",
            parameter_overrides={
                "temperature": ParameterOverride(action="drop"),
                "max_tokens": ParameterOverride(action="override", value=1000),
            },
            defaults={"top_p": 0.9},
        )

        config = {
            "model": "test-model",
            "temperature": 0.7,
            "max_tokens": 500,
            "frequency_penalty": 0.5,
        }

        result = override.apply_to_config(config)

        # temperature should be dropped
        assert "temperature" not in result
        # max_tokens should be overridden
        assert result["max_tokens"] == 1000
        # frequency_penalty should pass through
        assert result["frequency_penalty"] == 0.5
        # default should be added
        assert result["top_p"] == 0.9


class TestModelOverrideRegistry:
    def test_default_gpt5_overrides(self):
        # Test that GPT-5 models have temperature dropped
        registry = ModelOverrideRegistry()

        config = {"model": "gpt-5-mini", "temperature": 0.7, "max_tokens": 500}

        result = registry.apply("gpt-5-mini", config)

        # Temperature should be dropped for GPT-5
        assert "temperature" not in result
        assert result["max_tokens"] == 500

    def test_default_claude_overrides(self):
        registry = ModelOverrideRegistry()

        config = {
            "model": "claude-3-5-sonnet",
            "logit_bias": {"test": 1.0},
            "n": 2,
            "temperature": 0.7,
        }

        result = registry.apply("claude-3-5-sonnet-20241022", config)

        # Claude doesn't support logit_bias or n
        assert "logit_bias" not in result
        assert "n" not in result
        # Temperature should pass through
        assert result["temperature"] == 0.7
        # Default max_tokens should be added
        assert result["max_tokens"] == 8192

    def test_default_o1_overrides(self):
        registry = ModelOverrideRegistry()

        config = {
            "model": "o1-preview",
            "temperature": 0.7,
            "top_p": 0.9,
            "presence_penalty": 0.5,
            "frequency_penalty": 0.5,
        }

        result = registry.apply("o1-preview", config)

        # o1 models force temperature and top_p to 1.0
        assert result["temperature"] == 1.0
        assert result["top_p"] == 1.0
        # Penalties should be dropped
        assert "presence_penalty" not in result
        assert "frequency_penalty" not in result
        # Default max_completion_tokens should be added
        assert result["max_completion_tokens"] == 32768

    def test_custom_override_registration(self):
        registry = ModelOverrideRegistry()

        # Register a custom override
        custom_override = ModelOverride(
            model_pattern="custom-model*",
            parameter_overrides={"custom_param": ParameterOverride(action="drop")},
        )
        registry.register(custom_override)

        config = {
            "model": "custom-model-v1",
            "custom_param": "should_be_removed",
            "other_param": "should_stay",
        }

        result = registry.apply("custom-model-v1", config)

        assert "custom_param" not in result
        assert result["other_param"] == "should_stay"

    def test_get_model_info(self):
        registry = ModelOverrideRegistry()

        info = registry.get_model_info("gpt-5-mini")

        assert info["model"] == "gpt-5-mini"
        assert "gpt-5*" in info["overrides"]
        assert "temperature" in info["dropped_parameters"]

        info = registry.get_model_info("o1-mini")

        assert info["model"] == "o1-mini"
        assert "o1*" in info["overrides"]
        assert info["forced_parameters"]["temperature"] == 1.0
        assert info["forced_parameters"]["top_p"] == 1.0
        assert info["defaults"]["max_completion_tokens"] == 32768

    def test_no_matching_override(self):
        registry = ModelOverrideRegistry()

        config = {"model": "unknown-model", "temperature": 0.7, "max_tokens": 500}

        result = registry.apply("unknown-model", config)

        # Config should pass through unchanged
        assert result == config


class TestModelCapabilities:
    def test_model_capabilities_dataclass(self):
        from good_agent.model.overrides import ModelCapabilities

        caps = ModelCapabilities(function_calling=True, images=True, streaming=False)

        assert caps.function_calling is True
        assert caps.images is True
        assert caps.streaming is False
        assert caps.pdf_input is False  # Default value

        # Test to_dict
        caps_dict = caps.to_dict()
        assert caps_dict["function_calling"] is True
        assert caps_dict["images"] is True
        assert caps_dict["streaming"] is False

    def test_get_model_capabilities(self):
        from good_agent.model.overrides import ModelOverrideRegistry

        registry = ModelOverrideRegistry()

        # Test GPT-5 capabilities
        gpt5_caps = registry.get_model_capabilities("gpt-5-mini")
        assert gpt5_caps.function_calling is True
        assert gpt5_caps.parallel_function_calling is True
        assert gpt5_caps.images is True
        assert gpt5_caps.web_search is True

        # Test Claude capabilities
        claude_caps = registry.get_model_capabilities("claude-3-5-sonnet-20241022")
        assert claude_caps.function_calling is True
        assert claude_caps.parallel_function_calling is False  # Claude doesn't support parallel
        assert claude_caps.context_caching is True
        assert claude_caps.pdf_input is True

        # Test o1 capabilities
        o1_caps = registry.get_model_capabilities("o1-preview")
        assert o1_caps.function_calling is True
        assert o1_caps.streaming is False  # o1 doesn't support streaming
        assert o1_caps.thinking is True  # o1 has thinking tokens

        # Test unknown model (should return default capabilities)
        unknown_caps = registry.get_model_capabilities("unknown-model")
        assert unknown_caps.function_calling is False
        assert unknown_caps.streaming is True  # Default is True

    def test_model_info_includes_capabilities(self):
        from good_agent.model.overrides import ModelOverrideRegistry

        registry = ModelOverrideRegistry()
        info = registry.get_model_info("gemini-pro")

        assert "capabilities" in info
        assert info["capabilities"]["function_calling"] is True
        assert info["capabilities"]["video_input"] is True
        assert info["capabilities"]["audio_input"] is True


class TestIntegrationWithLanguageModel:
    @pytest.mark.asyncio
    async def test_model_overrides_in_prepare_config(self):
        import os
        import sys

        tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        sys.path.insert(0, os.path.join(tests_dir, "fixtures", "helpers"))
        from good_agent.model.llm import LanguageModel
        from test_helpers import MockAgent  # type: ignore[import-not-found]

        # Create mock agent with the configuration
        mock_agent = MockAgent(model="gpt-5-mini")
        llm = LanguageModel()
        mock_agent.install_component(llm)

        # Get prepared config - should have temperature dropped
        prepared = llm._prepare_request_config(temperature=0.7)

        assert "temperature" not in prepared
        assert prepared["model"] == "gpt-5-mini"

    def test_register_model_override_classmethod(self):
        from good_agent.model.llm import LanguageModel

        # Register a test override
        test_override = ModelOverride(
            model_pattern="test-llm*",
            parameter_overrides={"test_param": ParameterOverride(action="drop")},
        )

        LanguageModel.register_model_override(test_override)

        # Check it was registered
        info = LanguageModel.get_model_overrides("test-llm-v1")
        assert "test-llm*" in info["overrides"]
        assert "test_param" in info["dropped_parameters"]

    def test_capability_checking_methods(self):
        import os
        import sys

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from good_agent.model.llm import LanguageModel
        from good_agent.model.overrides import ModelCapabilities, ModelOverride
        from test_helpers import MockAgent  # type: ignore[import-not-found]

        # Register a test model with specific capabilities
        test_override = ModelOverride(
            model_pattern="test-caps-model",
            parameter_overrides={},
            capabilities=ModelCapabilities(
                function_calling=True,
                parallel_function_calling=False,
                images=True,
                pdf_input=True,
                streaming=False,
                audio_input=True,
                audio_output=False,
                video_input=True,
                web_search=True,
                context_caching=True,
            ),
        )

        LanguageModel.register_model_override(test_override)

        # Create mock agent with the configuration
        mock_agent = MockAgent(model="test-caps-model")
        llm = LanguageModel()
        mock_agent.install_component(llm)

        # Test individual capability methods
        assert llm.supports_function_calling() is True
        assert llm.supports_parallel_function_calling() is False
        assert llm.supports_images() is True
        assert llm.supports_pdf_input() is True
        assert llm.supports_streaming() is False
        assert llm.supports_video() is True
        assert llm.supports_web_search() is True
        assert llm.supports_context_caching() is True

        # Test audio (returns tuple)
        audio_in, audio_out = llm.supports_audio()
        assert audio_in is True
        assert audio_out is False

        # Test get_capabilities
        all_caps = llm.get_capabilities()
        assert all_caps["function_calling"] is True
        assert all_caps["parallel_function_calling"] is False
        assert all_caps["streaming"] is False

    def test_capability_checking_with_model_override(self):
        import os
        import sys

        tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        sys.path.insert(0, os.path.join(tests_dir, "fixtures", "helpers"))
        from good_agent.model.llm import LanguageModel
        from test_helpers import MockAgent  # type: ignore[import-not-found]

        # Create mock agent with the configuration
        mock_agent = MockAgent(model="gpt-4")
        llm = LanguageModel()
        mock_agent.install_component(llm)

        # Check capabilities for different models
        assert llm.supports_function_calling("gpt-5-mini") is True
        assert llm.supports_streaming("o1-preview") is False
        assert llm.supports_parallel_function_calling("claude-3-5-sonnet-20241022") is False
        assert llm.supports_video("gemini-pro") is True
