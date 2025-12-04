import asyncio
import inspect
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast, overload
from weakref import WeakValueDictionary

from good_agent.model.overrides import (
    ModelOverride,
    model_override_registry,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from litellm.files.main import ModelResponse
    from litellm.integrations.custom_logger import CustomLogger
    from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
    from litellm.router import Router


@dataclass
class ModelDefinition:
    """Definition for a custom model."""

    name: str
    provider: str
    api_base: str | None = None
    api_key: str | None = None
    input_cost_per_token: float = 0.0
    output_cost_per_token: float = 0.0
    max_tokens: int = 4096
    supports_function_calling: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    custom_llm_provider: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_litellm_params(self) -> dict[str, Any]:
        """Convert to litellm model parameters."""
        params = {
            "model": self.name,
            "litellm_provider": self.provider,
            "input_cost_per_token": self.input_cost_per_token,
            "output_cost_per_token": self.output_cost_per_token,
            "max_tokens": self.max_tokens,
            "supports_function_calling": self.supports_function_calling,
            "supports_vision": self.supports_vision,
            "supports_streaming": self.supports_streaming,
        }

        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key
        if self.custom_llm_provider:
            params["custom_llm_provider"] = self.custom_llm_provider

        params.update(self.extra_params)
        return params

    def to_deployment(self) -> dict[str, Any]:
        """Convert to litellm deployment configuration."""
        return {"model_name": self.name, "litellm_params": self.to_litellm_params()}


# Global variable to store the actual ManagedRouter class
_ManagedRouterClass = None


CallbackFunc = Callable[..., Any]


@contextmanager
def _temporarily_patch_callbacks(
    callback_manager: Any, replacements: dict[str, CallbackFunc]
) -> Iterator[None]:
    """Temporarily replace callback manager methods and restore them afterward."""

    originals: dict[str, CallbackFunc] = {}
    for attr, replacement in replacements.items():
        originals[attr] = getattr(callback_manager, attr)
        setattr(callback_manager, attr, replacement)

    try:
        yield
    finally:
        for attr, original in originals.items():
            setattr(callback_manager, attr, original)


def get_managed_router_class():
    """Get or create the ManagedRouter class with lazy loading."""
    global _ManagedRouterClass

    if _ManagedRouterClass is None:
        # Import Router only when first needed
        from litellm.router import Router

        class _ManagedRouter(Router):
            """
            Extended Router with managed callback handling for true isolation.

            This Router subclass maintains all of litellm Router's functionality
            while providing complete callback isolation between instances. Callbacks
            are managed per-instance and invoked manually, bypassing litellm's global
            callback system.

            Note: LiteLLM internally tracks deployment callbacks and has a hard limit
            of 30. To avoid hitting this limit, we override the deployment callbacks
            with no-ops BEFORE Router.__init__ is called, preventing any global registration.
            We handle all callbacks manually through _managed_callbacks.
            """

            # Override deployment callbacks as class methods to prevent global registration
            def deployment_callback_on_failure(self, *args, **kwargs) -> bool:
                """No-op replacement for deployment callbacks that expect bool return."""
                return True

            async def async_deployment_callback_on_failure(self, *args, **kwargs) -> None:
                """Async no-op replacement for deployment callbacks."""
                pass

            async def deployment_callback_on_success(self, *args, **kwargs) -> None:
                """Async no-op replacement for deployment callbacks."""
                pass

            def sync_deployment_callback_on_success(self, *args, **kwargs) -> str | None:
                """No-op replacement for deployment callbacks that expect str|None return."""
                return None

            async def async_deployment_callback_on_success(self, *args, **kwargs) -> None:
                """Async no-op replacement for deployment callbacks."""
                pass

            def __init__(
                self,
                model_list: list[dict[str, Any]] | None = None,
                managed_callbacks: list[CustomLogger] | None = None,
                **router_kwargs,
            ):
                """
                Initialize the managed router.

                Args:
                    model_list: List of model deployments
                    managed_callbacks: List of callbacks specific to this instance
                    **router_kwargs: Additional Router initialization parameters
                """
                # Initialize our managed callbacks before Router init
                self._managed_callbacks = managed_callbacks or []

                # Track if we're using instructor
                self._instructor_client = None

                # Track active requests for debugging
                self._active_requests = 0

                # No need to assign callbacks - they're already overridden as class methods

                # HACK: Temporarily monkey-patch litellm's callback manager to prevent registration
                import litellm

                # Replace with no-ops during Router.__init__
                def noop_add(*args, **kwargs):
                    pass

                callback_manager = litellm.logging_callback_manager
                replacements = {
                    "add_litellm_async_success_callback": noop_add,
                    "add_litellm_success_callback": noop_add,
                    "add_litellm_async_failure_callback": noop_add,
                    "add_litellm_failure_callback": noop_add,
                }

                # Initialize Router while callbacks are temporarily silenced
                with _temporarily_patch_callbacks(callback_manager, replacements):
                    super().__init__(model_list=model_list or [], **router_kwargs)

            async def _invoke_async_callbacks(self, method_name: str, *args, **kwargs):
                """
                Manually invoke an async callback method on all registered callbacks.

                Args:
                    method_name: Name of the async callback method to invoke
                    *args, **kwargs: Arguments to pass to the callback
                """
                for callback in self._managed_callbacks:
                    if hasattr(callback, method_name):
                        try:
                            method = getattr(callback, method_name)
                            if inspect.iscoroutinefunction(method):
                                await method(*args, **kwargs)
                            else:
                                method(*args, **kwargs)
                        except Exception as e:
                            logger.warning(
                                f"Callback {callback.__class__.__name__}.{method_name} failed: {e}"
                            )

            @overload
            async def acompletion(
                self,
                model: str,
                messages: list[Any],
                stream: Literal[True],
                **kwargs: Any,
            ) -> CustomStreamWrapper: ...

            @overload
            async def acompletion(
                self,
                model: str,
                messages: list[Any],
                stream: Literal[False] = ...,
                **kwargs: Any,
            ) -> ModelResponse: ...

            @overload
            async def acompletion(
                self, model: str, messages: list[Any], stream: bool = ..., **kwargs: Any
            ) -> ModelResponse | CustomStreamWrapper: ...

            async def acompletion(self, *args, **kwargs):
                """
                Overridden acompletion to handle callbacks manually.

                This method adds our managed callbacks just before the call,
                executes the completion, and removes them immediately after.
                This ensures complete isolation between router instances.
                """
                # Track active requests
                self._active_requests += 1

                try:
                    # Add callbacks for this request
                    # We add them globally temporarily because litellm needs them there
                    # But we'll remove them immediately after

                    # Actually, instead of manipulating global callbacks, we'll
                    # invoke callbacks manually at the right times

                    # Before the request
                    await self._invoke_async_callbacks(
                        "async_log_pre_api_call",
                        kwargs.get("model", args[0] if args else None),
                        args[1] if len(args) > 1 else kwargs.get("messages", []),
                        kwargs,
                    )

                    # Make the actual request to the parent Router
                    result = await super().acompletion(*args, **kwargs)

                    # After successful request
                    import time

                    end_time = time.time()
                    await self._invoke_async_callbacks(
                        "async_log_success_event",
                        kwargs,
                        result,
                        kwargs.get("start_time", end_time - 1),
                        end_time,
                    )

                    return result

                except Exception as e:
                    # On failure
                    import time

                    end_time = time.time()
                    await self._invoke_async_callbacks(
                        "async_log_failure_event",
                        kwargs,
                        e,
                        kwargs.get("start_time", end_time - 1),
                        end_time,
                    )
                    raise

                finally:
                    self._active_requests -= 1

            def patch_with_instructor(self, mode=None):
                """
                Patch the router with instructor for structured outputs.

                This is a no-op if already patched. Instructor will add
                extract and aextract methods to the router.

                Args:
                    mode: Optional instructor mode (e.g., Mode.TOOLS, Mode.JSON)
                """
                if self._instructor_client:
                    return self

                try:
                    import instructor

                    # Default to TOOLS mode if none specified
                    if mode is None:
                        mode = instructor.Mode.TOOLS

                    # Use instructor.from_litellm with our acompletion method
                    self._instructor_client = instructor.from_litellm(
                        self.acompletion,  # Pass our async completion method
                        mode=mode,
                    )
                    # Map instructor's methods to our expected interface
                    # Instructor uses 'create' for extraction, not 'aextract'
                    if self._instructor_client is not None and hasattr(
                        self._instructor_client, "create"
                    ):
                        self.aextract = self._instructor_client.create
                        self.extract = self._instructor_client.create  # Same for sync version
                except ImportError:
                    logger.warning("Instructor not installed, structured output unavailable")

                return self

            def add_callback(self, callback: CustomLogger) -> None:
                """
                Add a callback handler to this instance.

                Args:
                    callback: CustomLogger instance to add
                """
                if callback not in self._managed_callbacks:
                    self._managed_callbacks.append(callback)
                    logger.debug(f"Added callback: {callback.__class__.__name__}")

            def remove_callback(self, callback: CustomLogger) -> None:
                """
                Remove a callback handler from this instance.

                Args:
                    callback: CustomLogger instance to remove
                """
                if callback in self._managed_callbacks:
                    self._managed_callbacks.remove(callback)
                    logger.debug(f"Removed callback: {callback.__class__.__name__}")

            def clear_callbacks(self) -> None:
                """Clear all callbacks from this instance."""
                self._managed_callbacks.clear()
                logger.debug("Cleared all callbacks")

            def get_available_models(self) -> list[str]:
                """Get list of available model names."""
                return list(
                    {m.get("model_name", "") for m in self.model_list if m.get("model_name")}
                )

            def cleanup(self):
                """Clean up resources."""
                self.clear_callbacks()
                self._active_requests = 0

        _ManagedRouterClass = _ManagedRouter

    return _ManagedRouterClass


# Stub class for type hints
class ManagedRouter:
    """
    Stub class for type hints. Real implementation created lazily.

    This allows type checkers to work correctly while the actual
    class is only created when first needed, avoiding litellm imports.
    """

    def __init__(self, *args, **kwargs): ...
    def patch_with_instructor(self, mode=None): ...
    async def acompletion(self, *args, **kwargs): ...
    async def aextract(self, *args, **kwargs): ...
    def add_callback(self, callback): ...
    def remove_callback(self, callback): ...
    def clear_callbacks(self): ...
    def get_available_models(self): ...
    def cleanup(self): ...


# Factory function for creating ManagedRouter instances
def create_managed_router(*args, **kwargs) -> ManagedRouter:
    """Create a ManagedRouter instance with lazy loading."""
    RouterClass = get_managed_router_class()
    # Cast to ManagedRouter for type checking - the actual class extends Router
    return cast(ManagedRouter, RouterClass(*args, **kwargs))


# Global router pool to avoid LiteLLM's callback limit
_GLOBAL_ROUTER_POOL: list[Router] = []
_ROUTER_POOL_SIZE = 10
_router_pool_index = 0
_router_pool_lock = asyncio.Lock() if asyncio else None


def _get_or_create_base_router(model_list: list[dict[str, Any]]) -> Router:
    """Get a base Router from the pool or create one if under the limit.

    This helps avoid LiteLLM's internal callback limit (30) by reusing
    Router instances when possible.
    """
    global _router_pool_index

    # If we haven't hit the pool size limit, create a new router
    if len(_GLOBAL_ROUTER_POOL) < _ROUTER_POOL_SIZE:
        from litellm.router import Router

        router = Router(model_list=model_list)
        _GLOBAL_ROUTER_POOL.append(router)
        return router

    # Otherwise, reuse an existing router (round-robin)
    router = _GLOBAL_ROUTER_POOL[_router_pool_index]
    _router_pool_index = (_router_pool_index + 1) % len(_GLOBAL_ROUTER_POOL)

    # Update the model list
    router.model_list = model_list

    return router


class ModelManager:
    """
    Model manager for registering and managing LLM models.

    This class provides:
    1. Model registration for custom models
    2. Model override configuration
    3. Router factory with proper callback isolation
    """

    def __init__(self):
        """Initialize the model manager."""
        self._models: dict[str, ModelDefinition] = {}
        self._overrides = model_override_registry
        self._router_pool: WeakValueDictionary[int, ManagedRouter] = WeakValueDictionary()

    def register_model(self, name: str, provider: str, **kwargs) -> None:
        """
        Register a custom model definition.

        Args:
            name: Model name
            provider: Provider name (e.g., "openai", "anthropic")
            **kwargs: Additional model parameters
        """
        model_def = ModelDefinition(name=name, provider=provider, **kwargs)
        self._models[name] = model_def

        # Also register with litellm's model cost tracking if costs provided
        if model_def.input_cost_per_token or model_def.output_cost_per_token:
            try:
                import litellm

                litellm.model_cost[name] = {
                    "input_cost_per_token": model_def.input_cost_per_token,
                    "output_cost_per_token": model_def.output_cost_per_token,
                }
            except Exception as e:
                logger.debug(f"Could not register model costs with litellm: {e}")

    def register_override(self, override: ModelOverride) -> None:
        """
        Register a model override.

        Args:
            override: ModelOverride instance
        """
        self._overrides.register(override)

    def create_router(
        self,
        primary_model: str,
        fallback_models: list[str] | None = None,
        managed_callbacks: list[CustomLogger] | None = None,
        **router_kwargs,
    ) -> ManagedRouter:
        """
        Create a new ManagedRouter with callback isolation.

        Args:
            primary_model: Primary model name
            fallback_models: Optional list of fallback models
            managed_callbacks: Optional list of callbacks for this instance
            **router_kwargs: Additional router configuration

        Returns:
            ManagedRouter instance with isolated callbacks
        """
        # Build model list
        model_list = []

        # Add primary model
        if primary_model in self._models:
            model_list.append(self._models[primary_model].to_deployment())
        else:
            model_list.append(
                {
                    "model_name": primary_model,
                    "litellm_params": {"model": primary_model},
                }
            )

        # Add fallbacks
        if fallback_models:
            for fallback in fallback_models:
                if fallback in self._models:
                    model_list.append(self._models[fallback].to_deployment())
                else:
                    model_list.append(
                        {"model_name": fallback, "litellm_params": {"model": fallback}}
                    )

        # Create router with isolated callbacks
        router = create_managed_router(
            model_list=model_list, managed_callbacks=managed_callbacks, **router_kwargs
        )

        # Track in our pool
        self._router_pool[id(router)] = router

        return router

    def get_model_info(self, model_name: str) -> dict[str, Any]:
        """
        Get information about a model.

        Args:
            model_name: Model name

        Returns:
            Dictionary with model information
        """
        info = {}

        # Check if it's a registered model
        if model_name in self._models:
            model_def = self._models[model_name]
            info.update(model_def.to_litellm_params())

        # Add override information
        override_info = self._overrides.get_model_info(model_name)
        info.update(override_info)

        return info

    def list_models(self) -> list[str]:
        """
        List all registered model names.

        Returns:
            List of model names
        """
        # Combine registered models with those known to have overrides
        all_models = set(self._models.keys())
        for override in self._overrides._overrides:
            if hasattr(override, "pattern"):
                # Can't list all possible pattern matches
                continue
            elif hasattr(override, "model_pattern") and "*" not in override.model_pattern:
                # Only add exact model names, not patterns
                all_models.add(override.model_pattern)

        return sorted(all_models)

    def cleanup_router(self, router: ManagedRouter) -> None:
        """
        Clean up a router instance.

        Args:
            router: Router to clean up
        """
        if hasattr(router, "cleanup"):
            router.cleanup()
        # Remove from pool (WeakValueDictionary handles this automatically)
