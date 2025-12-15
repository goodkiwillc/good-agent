"""Model capability detection and validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from good_agent.model.llm import LanguageModel


class ModelCapabilities:
    """Model capability detection for feature support checking.

    Provides methods to check if a model supports various features like
    function calling, vision, streaming, etc.
    """

    def __init__(self, language_model: LanguageModel):
        """Initialize capabilities checker.

        Args:
            language_model: Parent LanguageModel instance
        """
        self.llm = language_model

    def supports_function_calling(self, model: str | None = None) -> bool:
        """Check if the model supports function calling"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model

        # Check our registry first (it has precedence for custom models)
        capabilities = model_override_registry.get_model_capabilities(model_name)

        # If we have a specific override, use it
        if any(override.matches(model_name) for override in model_override_registry._overrides):
            return capabilities.function_calling

        # Otherwise try litellm
        try:
            return self.llm.litellm.supports_function_calling(model_name)
        except (AttributeError, Exception):
            # Fall back to our capability value
            return capabilities.function_calling

    def supports_parallel_function_calling(self, model: str | None = None) -> bool:
        """Check if the model supports parallel function calling"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model

        # Check our registry first (it has precedence for custom models)
        capabilities = model_override_registry.get_model_capabilities(model_name)

        # If we have a specific override, use it
        if any(override.matches(model_name) for override in model_override_registry._overrides):
            return capabilities.parallel_function_calling

        # Otherwise try litellm
        try:
            return self.llm.litellm.supports_parallel_function_calling(model_name)
        except (AttributeError, Exception):
            # Fall back to our capability value
            return capabilities.parallel_function_calling

    def supports_images(self, model: str | None = None) -> bool:
        """Check if the model supports image inputs"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model

        # Check our registry first (it has precedence for custom models)
        capabilities = model_override_registry.get_model_capabilities(model_name)

        # If we have a specific override, use it
        if any(override.matches(model_name) for override in model_override_registry._overrides):
            return capabilities.vision

        # Otherwise try litellm's vision support if available
        try:
            if hasattr(self.llm.litellm, "supports_vision"):
                return self.llm.litellm.supports_vision(model_name)
        except Exception:
            pass

        # Fall back to our capability value
        return capabilities.vision

    def supports_pdf_input(self, model: str | None = None) -> bool:
        """Check if the model supports PDF inputs"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.pdf_input

    def supports_citations(self, model: str | None = None) -> bool:
        """Check if the model supports citations"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.citations

    def supports_structured_output(self, model: str | None = None) -> bool:
        """Check if the model supports structured output (JSON mode, etc.)"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.response_schema

    def supports_streaming(self, model: str | None = None) -> bool:
        """Check if the model supports streaming responses"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.native_streaming

    def supports_audio(self, model: str | None = None) -> tuple[bool, bool]:
        """Check if the model supports audio input/output

        Returns:
            Tuple of (supports_audio_input, supports_audio_output)
        """
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.audio_input, capabilities.audio_output

    def supports_video(self, model: str | None = None) -> bool:
        """Check if the model supports video inputs"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.video_input

    def supports_web_search(self, model: str | None = None) -> bool:
        """Check if the model supports web search"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.web_search

    def supports_context_caching(self, model: str | None = None) -> bool:
        """Check if the model supports context/prompt caching"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.prompt_caching

    def supports_reasoning(self, model: str | None = None) -> bool:
        """Check if the model supports advanced reasoning modes"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.reasoning

    def get_capabilities(self, model: str | None = None) -> dict[str, Any]:
        """Get all capabilities for a model as a dictionary"""
        from good_agent.model.overrides import model_override_registry

        model_name = model or self.llm.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.to_dict()


__all__ = ["ModelCapabilities"]
