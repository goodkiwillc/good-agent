# LLM Client Extensibility Design

## Overview

Design a highly extensible architecture that supports:
1. **Adding new providers** (Google Vertex, Cohere, etc.)
2. **Adding new capabilities** (embeddings, image generation, etc.)
3. **Custom extensions** (middleware, transformers, hooks)
4. **Maintaining simplicity** for common use cases

## Core Principles

1. **Capability-Based** - Providers declare what they support
2. **Protocol-Driven** - Use Python protocols, not inheritance
3. **Lazy Loading** - Import only what's used
4. **Plugin Architecture** - Easy registration without modifying core
5. **Type-Safe** - Full typing support with runtime validation

## Architecture Overview

```
good_agent.llm_client/
├── __init__.py                    # Public API with lazy loading
├── capabilities/                  # Capability definitions (protocols)
│   ├── __init__.py               # Capability registry
│   ├── chat.py                   # Chat completion protocol
│   ├── embeddings.py             # Embeddings protocol
│   ├── images.py                 # Image generation protocol
│   └── audio.py                  # Audio (STT/TTS) protocol
├── providers/                     # Provider implementations
│   ├── __init__.py               # Provider registry
│   ├── base.py                   # Base provider class
│   ├── openai/
│   │   ├── __init__.py
│   │   ├── chat.py               # OpenAI chat implementation
│   │   ├── embeddings.py         # OpenAI embeddings
│   │   └── images.py             # OpenAI DALL-E
│   ├── anthropic/
│   │   ├── __init__.py
│   │   └── chat.py               # Anthropic chat only
│   ├── google/
│   │   ├── __init__.py
│   │   ├── chat.py               # Vertex AI chat
│   │   └── embeddings.py         # Vertex AI embeddings
│   └── cohere/
│       ├── __init__.py
│       ├── chat.py
│       └── embeddings.py
├── router.py                      # Multi-capability router
├── middleware/                    # Extension points
│   ├── __init__.py
│   ├── base.py                   # Middleware protocol
│   ├── logging.py                # Logging middleware
│   ├── caching.py                # Response caching
│   └── retry.py                  # Retry logic
├── types/                         # Type definitions by capability
│   ├── __init__.py
│   ├── common.py                 # Shared types
│   ├── chat.py                   # Chat-specific types
│   ├── embeddings.py             # Embedding types
│   └── images.py                 # Image types
└── utils/
    ├── tokens.py                 # Token counting
    └── costs.py                  # Cost calculation
```

## 1. Capability-Based Architecture

### Capability Protocols

**File: `capabilities/chat.py`**

```python
"""Chat completion capability protocol."""

from typing import Protocol, AsyncIterator, Any, runtime_checkable
from ..types.chat import ChatRequest, ChatResponse, StreamChunk


@runtime_checkable
class ChatCapability(Protocol):
    """Protocol for chat completion capability.
    
    Providers implementing this protocol support chat/text generation.
    """
    
    async def chat_complete(
        self,
        request: ChatRequest,
        **kwargs: Any
    ) -> ChatResponse:
        """Execute a chat completion request.
        
        Args:
            request: Chat completion request
            **kwargs: Provider-specific parameters
            
        Returns:
            Chat completion response
        """
        ...
    
    async def chat_stream(
        self,
        request: ChatRequest,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion request.
        
        Args:
            request: Chat completion request
            **kwargs: Provider-specific parameters
            
        Yields:
            Stream chunks
        """
        ...
    
    def supports_chat_streaming(self, model: str) -> bool:
        """Check if model supports streaming."""
        ...
    
    def supports_tools(self, model: str) -> bool:
        """Check if model supports function/tool calling."""
        ...
    
    def count_chat_tokens(
        self, 
        request: ChatRequest,
        model: str
    ) -> int:
        """Count tokens in chat request."""
        ...


@runtime_checkable
class ChatCapabilitySync(Protocol):
    """Synchronous chat capability for providers that don't support async."""
    
    def chat_complete_sync(
        self,
        request: ChatRequest,
        **kwargs: Any
    ) -> ChatResponse:
        """Synchronous chat completion."""
        ...
```

**File: `capabilities/embeddings.py`**

```python
"""Embeddings capability protocol."""

from typing import Protocol, runtime_checkable, Any
from ..types.embeddings import EmbeddingRequest, EmbeddingResponse


@runtime_checkable
class EmbeddingsCapability(Protocol):
    """Protocol for embeddings capability.
    
    Providers implementing this protocol support text embeddings.
    """
    
    async def create_embeddings(
        self,
        request: EmbeddingRequest,
        **kwargs: Any
    ) -> EmbeddingResponse:
        """Create embeddings for input texts.
        
        Args:
            request: Embedding request with texts
            **kwargs: Provider-specific parameters
            
        Returns:
            Embedding response with vectors
        """
        ...
    
    def get_embedding_dimensions(self, model: str) -> int:
        """Get embedding vector dimensions for model."""
        ...
    
    def get_max_batch_size(self, model: str) -> int:
        """Get maximum batch size for embeddings."""
        ...
    
    def count_embedding_tokens(
        self,
        texts: list[str],
        model: str
    ) -> int:
        """Count tokens for embedding request."""
        ...


@runtime_checkable
class EmbeddingsCapabilitySync(Protocol):
    """Synchronous embeddings capability."""
    
    def create_embeddings_sync(
        self,
        request: EmbeddingRequest,
        **kwargs: Any
    ) -> EmbeddingResponse:
        """Synchronous embeddings creation."""
        ...
```

**File: `capabilities/images.py`**

```python
"""Image generation capability protocol."""

from typing import Protocol, runtime_checkable, Any
from ..types.images import ImageRequest, ImageResponse


@runtime_checkable
class ImageGenerationCapability(Protocol):
    """Protocol for image generation capability.
    
    Providers implementing this protocol support image generation.
    """
    
    async def generate_images(
        self,
        request: ImageRequest,
        **kwargs: Any
    ) -> ImageResponse:
        """Generate images from prompt.
        
        Args:
            request: Image generation request
            **kwargs: Provider-specific parameters
            
        Returns:
            Generated images
        """
        ...
    
    def supports_image_sizes(self, model: str) -> list[tuple[int, int]]:
        """Get supported image sizes for model."""
        ...
    
    def supports_image_variations(self, model: str) -> bool:
        """Check if model supports image variations."""
        ...
```

### Capability Registry

**File: `capabilities/__init__.py`**

```python
"""Capability registry and discovery."""

from typing import Type, Protocol, get_args, runtime_checkable
from enum import Enum


class Capability(str, Enum):
    """Supported capabilities."""
    CHAT = "chat"
    EMBEDDINGS = "embeddings"
    IMAGE_GENERATION = "image_generation"
    AUDIO_STT = "audio_stt"  # Speech to text
    AUDIO_TTS = "audio_tts"  # Text to speech


# Map capabilities to their protocol types
CAPABILITY_PROTOCOLS = {
    Capability.CHAT: "ChatCapability",
    Capability.EMBEDDINGS: "EmbeddingsCapability",
    Capability.IMAGE_GENERATION: "ImageGenerationCapability",
}


def get_provider_capabilities(provider: Any) -> set[Capability]:
    """Discover which capabilities a provider supports.
    
    Args:
        provider: Provider instance
        
    Returns:
        Set of supported capabilities
    """
    from .chat import ChatCapability
    from .embeddings import EmbeddingsCapability
    from .images import ImageGenerationCapability
    
    capabilities = set()
    
    if isinstance(provider, ChatCapability):
        capabilities.add(Capability.CHAT)
    
    if isinstance(provider, EmbeddingsCapability):
        capabilities.add(Capability.EMBEDDINGS)
    
    if isinstance(provider, ImageGenerationCapability):
        capabilities.add(Capability.IMAGE_GENERATION)
    
    return capabilities


def requires_capability(capability: Capability):
    """Decorator to check if provider supports capability."""
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            capabilities = get_provider_capabilities(self)
            if capability not in capabilities:
                raise NotImplementedError(
                    f"Provider {self.__class__.__name__} does not support {capability}"
                )
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator
```

## 2. Base Provider Architecture

**File: `providers/base.py`**

```python
"""Base provider class with capability composition."""

from typing import Any, Optional
from abc import ABC, abstractmethod
from ..capabilities import Capability, get_provider_capabilities


class BaseProvider(ABC):
    """Base class for all LLM providers.
    
    Providers should implement capability protocols (ChatCapability, etc.)
    rather than inheriting specific methods.
    """
    
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        **kwargs: Any
    ):
        """Initialize provider.
        
        Args:
            api_key: API key for provider
            base_url: Custom base URL (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.config = kwargs
        
        # Discovered capabilities
        self._capabilities: set[Capability] | None = None
    
    @property
    def capabilities(self) -> set[Capability]:
        """Get provider capabilities (cached)."""
        if self._capabilities is None:
            self._capabilities = get_provider_capabilities(self)
        return self._capabilities
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name."""
        ...
    
    def supports_capability(self, capability: Capability) -> bool:
        """Check if provider supports capability."""
        return capability in self.capabilities
    
    def get_models(self, capability: Capability | None = None) -> list[str]:
        """Get available models, optionally filtered by capability.
        
        Args:
            capability: Filter by capability (None = all models)
            
        Returns:
            List of model names
        """
        return []  # Override in subclasses


class ProviderConfig:
    """Configuration for provider initialization."""
    
    def __init__(
        self,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.extra = kwargs
```

## 3. Example Provider: OpenAI (Multi-Capability)

**File: `providers/openai/__init__.py`**

```python
"""OpenAI provider with multiple capabilities."""

from .chat import OpenAIChatProvider
from .embeddings import OpenAIEmbeddingsProvider
from .images import OpenAIImagesProvider
from .provider import OpenAIProvider

__all__ = [
    'OpenAIProvider',
    'OpenAIChatProvider',
    'OpenAIEmbeddingsProvider',
    'OpenAIImagesProvider',
]
```

**File: `providers/openai/provider.py`**

```python
"""Unified OpenAI provider with all capabilities."""

from typing import Any, AsyncIterator
from openai import AsyncOpenAI

from ..base import BaseProvider
from ...capabilities import Capability
from ...capabilities.chat import ChatCapability
from ...capabilities.embeddings import EmbeddingsCapability
from ...capabilities.images import ImageGenerationCapability
from ...types.chat import ChatRequest, ChatResponse, StreamChunk
from ...types.embeddings import EmbeddingRequest, EmbeddingResponse
from ...types.images import ImageRequest, ImageResponse

from .chat import OpenAIChatProvider
from .embeddings import OpenAIEmbeddingsProvider
from .images import OpenAIImagesProvider


class OpenAIProvider(
    BaseProvider,
    ChatCapability,
    EmbeddingsCapability,
    ImageGenerationCapability
):
    """Unified OpenAI provider supporting multiple capabilities.
    
    This provider implements chat, embeddings, and image generation
    by composing specialized providers.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Create SDK client (shared across capabilities)
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        
        # Compose capability-specific providers
        self._chat = OpenAIChatProvider(self._client)
        self._embeddings = OpenAIEmbeddingsProvider(self._client)
        self._images = OpenAIImagesProvider(self._client)
    
    def get_provider_name(self) -> str:
        return "openai"
    
    # ========================================================================
    # Chat Capability
    # ========================================================================
    
    async def chat_complete(
        self,
        request: ChatRequest,
        **kwargs: Any
    ) -> ChatResponse:
        """Delegate to chat provider."""
        return await self._chat.chat_complete(request, **kwargs)
    
    async def chat_stream(
        self,
        request: ChatRequest,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Delegate to chat provider."""
        async for chunk in self._chat.chat_stream(request, **kwargs):
            yield chunk
    
    def supports_chat_streaming(self, model: str) -> bool:
        return self._chat.supports_chat_streaming(model)
    
    def supports_tools(self, model: str) -> bool:
        return self._chat.supports_tools(model)
    
    def count_chat_tokens(
        self,
        request: ChatRequest,
        model: str
    ) -> int:
        return self._chat.count_chat_tokens(request, model)
    
    # ========================================================================
    # Embeddings Capability
    # ========================================================================
    
    async def create_embeddings(
        self,
        request: EmbeddingRequest,
        **kwargs: Any
    ) -> EmbeddingResponse:
        """Delegate to embeddings provider."""
        return await self._embeddings.create_embeddings(request, **kwargs)
    
    def get_embedding_dimensions(self, model: str) -> int:
        return self._embeddings.get_embedding_dimensions(model)
    
    def get_max_batch_size(self, model: str) -> int:
        return self._embeddings.get_max_batch_size(model)
    
    def count_embedding_tokens(
        self,
        texts: list[str],
        model: str
    ) -> int:
        return self._embeddings.count_embedding_tokens(texts, model)
    
    # ========================================================================
    # Image Generation Capability
    # ========================================================================
    
    async def generate_images(
        self,
        request: ImageRequest,
        **kwargs: Any
    ) -> ImageResponse:
        """Delegate to images provider."""
        return await self._images.generate_images(request, **kwargs)
    
    def supports_image_sizes(self, model: str) -> list[tuple[int, int]]:
        return self._images.supports_image_sizes(model)
    
    def supports_image_variations(self, model: str) -> bool:
        return self._images.supports_image_variations(model)
    
    def get_models(self, capability: Capability | None = None) -> list[str]:
        """Get available models filtered by capability."""
        if capability == Capability.CHAT:
            return [
                "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4",
                "gpt-3.5-turbo", "o1-preview", "o1-mini"
            ]
        elif capability == Capability.EMBEDDINGS:
            return [
                "text-embedding-3-large", "text-embedding-3-small",
                "text-embedding-ada-002"
            ]
        elif capability == Capability.IMAGE_GENERATION:
            return ["dall-e-3", "dall-e-2"]
        else:
            # All models
            return self.get_models(Capability.CHAT) + \
                   self.get_models(Capability.EMBEDDINGS) + \
                   self.get_models(Capability.IMAGE_GENERATION)
```

**File: `providers/openai/embeddings.py`**

```python
"""OpenAI embeddings implementation."""

from typing import Any
from openai import AsyncOpenAI

from ...types.embeddings import EmbeddingRequest, EmbeddingResponse, Embedding


class OpenAIEmbeddingsProvider:
    """OpenAI embeddings capability implementation."""
    
    MODELS = {
        "text-embedding-3-large": {"dimensions": 3072, "max_batch": 2048},
        "text-embedding-3-small": {"dimensions": 1536, "max_batch": 2048},
        "text-embedding-ada-002": {"dimensions": 1536, "max_batch": 2048},
    }
    
    def __init__(self, client: AsyncOpenAI):
        self._client = client
        self._tokenizer_cache = {}
    
    async def create_embeddings(
        self,
        request: EmbeddingRequest,
        **kwargs: Any
    ) -> EmbeddingResponse:
        """Create embeddings using OpenAI API."""
        response = await self._client.embeddings.create(
            input=request.texts,
            model=request.model,
            encoding_format=kwargs.get("encoding_format", "float"),
            **kwargs
        )
        
        # Convert to our format
        embeddings = [
            Embedding(
                index=item.index,
                embedding=item.embedding,
                object="embedding"
            )
            for item in response.data
        ]
        
        return EmbeddingResponse(
            object="list",
            data=embeddings,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        )
    
    def get_embedding_dimensions(self, model: str) -> int:
        """Get embedding dimensions for model."""
        model_info = self.MODELS.get(model)
        if model_info:
            return model_info["dimensions"]
        return 1536  # Default
    
    def get_max_batch_size(self, model: str) -> int:
        """Get max batch size for model."""
        model_info = self.MODELS.get(model)
        if model_info:
            return model_info["max_batch"]
        return 2048  # Default
    
    def count_embedding_tokens(
        self,
        texts: list[str],
        model: str
    ) -> int:
        """Count tokens for embedding request."""
        # Use tiktoken
        if model not in self._tokenizer_cache:
            import tiktoken
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")
            self._tokenizer_cache[model] = encoding
        
        encoding = self._tokenizer_cache[model]
        return sum(len(encoding.encode(text)) for text in texts)
```

## 4. Provider Registry with Capability Discovery

**File: `providers/__init__.py`**

```python
"""Provider registry with automatic capability discovery."""

from typing import Type, Any, Optional
from enum import Enum
import importlib
import logging

from .base import BaseProvider, ProviderConfig
from ..capabilities import Capability, get_provider_capabilities

logger = logging.getLogger(__name__)


class ProviderName(str, Enum):
    """Known provider names."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    OPENROUTER = "openrouter"


class ProviderRegistry:
    """Registry for provider discovery and instantiation."""
    
    def __init__(self):
        self._providers: dict[str, Type[BaseProvider]] = {}
        self._instances: dict[str, BaseProvider] = {}
        self._capability_index: dict[Capability, list[str]] = {}
    
    def register(
        self,
        name: str,
        provider_class: Type[BaseProvider],
        aliases: list[str] | None = None
    ) -> None:
        """Register a provider class.
        
        Args:
            name: Provider name
            provider_class: Provider class
            aliases: Alternative names
        """
        self._providers[name] = provider_class
        
        if aliases:
            for alias in aliases:
                self._providers[alias] = provider_class
        
        logger.debug(f"Registered provider: {name}")
    
    def get_provider_class(self, name: str) -> Type[BaseProvider]:
        """Get provider class by name.
        
        Args:
            name: Provider name
            
        Returns:
            Provider class
            
        Raises:
            ValueError: If provider not found
        """
        if name not in self._providers:
            # Try to lazy-load provider
            self._try_load_provider(name)
        
        if name not in self._providers:
            available = ", ".join(self._providers.keys())
            raise ValueError(
                f"Unknown provider: {name}. "
                f"Available: {available}"
            )
        
        return self._providers[name]
    
    def create_provider(
        self,
        config: ProviderConfig | str,
        **kwargs: Any
    ) -> BaseProvider:
        """Create provider instance.
        
        Args:
            config: Provider config or name
            **kwargs: Additional config parameters
            
        Returns:
            Provider instance
        """
        if isinstance(config, str):
            config = ProviderConfig(provider=config, **kwargs)
        
        provider_class = self.get_provider_class(config.provider)
        
        # Merge config
        init_kwargs = {
            "api_key": config.api_key,
            "base_url": config.base_url,
            **config.extra,
            **kwargs
        }
        
        return provider_class(**init_kwargs)
    
    def get_or_create_provider(
        self,
        name: str,
        **kwargs: Any
    ) -> BaseProvider:
        """Get cached provider or create new instance.
        
        Args:
            name: Provider name
            **kwargs: Config parameters
            
        Returns:
            Provider instance (cached)
        """
        cache_key = f"{name}:{hash(frozenset(kwargs.items()))}"
        
        if cache_key not in self._instances:
            self._instances[cache_key] = self.create_provider(name, **kwargs)
        
        return self._instances[cache_key]
    
    def find_providers_with_capability(
        self,
        capability: Capability
    ) -> list[str]:
        """Find all providers supporting a capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of provider names
        """
        # Build capability index if needed
        if not self._capability_index:
            self._build_capability_index()
        
        return self._capability_index.get(capability, [])
    
    def _build_capability_index(self) -> None:
        """Build index of capabilities -> providers."""
        for name, provider_class in self._providers.items():
            # Create temporary instance to discover capabilities
            try:
                instance = provider_class()
                capabilities = get_provider_capabilities(instance)
                
                for cap in capabilities:
                    if cap not in self._capability_index:
                        self._capability_index[cap] = []
                    if name not in self._capability_index[cap]:
                        self._capability_index[cap].append(name)
            except Exception as e:
                logger.warning(
                    f"Could not discover capabilities for {name}: {e}"
                )
    
    def _try_load_provider(self, name: str) -> None:
        """Try to lazy-load provider module."""
        try:
            module = importlib.import_module(f".{name}", package=__package__)
            
            # Look for provider class
            if hasattr(module, f"{name.title()}Provider"):
                provider_class = getattr(module, f"{name.title()}Provider")
                self.register(name, provider_class)
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not lazy-load provider {name}: {e}")
    
    def list_providers(self) -> list[str]:
        """List all registered providers."""
        return sorted(set(self._providers.keys()))


# Global registry instance
_registry = ProviderRegistry()


# Registration API
def register_provider(
    name: str,
    provider_class: Type[BaseProvider],
    aliases: list[str] | None = None
) -> None:
    """Register a custom provider.
    
    Example:
        ```python
        from good_agent.llm_client.providers import register_provider
        from good_agent.llm_client.providers.base import BaseProvider
        
        class MyCustomProvider(BaseProvider, ChatCapability):
            # ... implementation ...
        
        register_provider("custom", MyCustomProvider)
        ```
    """
    _registry.register(name, provider_class, aliases)


def get_provider(
    name: str,
    **kwargs: Any
) -> BaseProvider:
    """Get or create provider instance.
    
    Example:
        ```python
        provider = get_provider("openai", api_key="sk-...")
        ```
    """
    return _registry.get_or_create_provider(name, **kwargs)


def find_providers(capability: Capability) -> list[str]:
    """Find providers supporting a capability.
    
    Example:
        ```python
        # Find all providers with embeddings
        providers = find_providers(Capability.EMBEDDINGS)
        # ["openai", "cohere", "google"]
        ```
    """
    return _registry.find_providers_with_capability(capability)


# Pre-register known providers
def _register_builtin_providers():
    """Register built-in providers."""
    try:
        from .openai import OpenAIProvider
        _registry.register("openai", OpenAIProvider)
    except ImportError:
        pass
    
    try:
        from .anthropic import AnthropicProvider
        _registry.register("anthropic", AnthropicProvider, ["claude"])
    except ImportError:
        pass


# Register on module import
_register_builtin_providers()
```

## 5. Multi-Capability Router

**File: `router.py`**

```python
"""Multi-capability router with provider fallback."""

from typing import Any, AsyncIterator, Optional
import logging

from .capabilities import Capability
from .providers import get_provider
from .providers.base import BaseProvider
from .types.chat import ChatRequest, ChatResponse, StreamChunk
from .types.embeddings import EmbeddingRequest, EmbeddingResponse
from .types.images import ImageRequest, ImageResponse
from .exceptions import ProviderError

logger = logging.getLogger(__name__)


class UnifiedRouter:
    """Router supporting multiple capabilities with fallback.
    
    Example:
        ```python
        router = UnifiedRouter(
            chat_config={
                "primary": "gpt-4o",
                "fallbacks": ["gpt-4-turbo", "claude-3.5-sonnet"]
            },
            embeddings_config={
                "primary": "text-embedding-3-large"
            }
        )
        
        # Chat
        response = await router.chat(messages, model="gpt-4o")
        
        # Embeddings
        embeddings = await router.embed(["text1", "text2"])
        ```
    """
    
    def __init__(
        self,
        chat_config: dict[str, Any] | None = None,
        embeddings_config: dict[str, Any] | None = None,
        images_config: dict[str, Any] | None = None,
        **provider_kwargs
    ):
        """Initialize multi-capability router.
        
        Args:
            chat_config: Chat capability configuration
            embeddings_config: Embeddings capability configuration
            images_config: Image generation capability configuration
            **provider_kwargs: Shared provider configuration (api_key, etc.)
        """
        self.chat_config = chat_config or {}
        self.embeddings_config = embeddings_config or {}
        self.images_config = images_config or {}
        self.provider_kwargs = provider_kwargs
        
        self._providers: dict[str, BaseProvider] = {}
        self._stats = {
            "chat_calls": 0,
            "embeddings_calls": 0,
            "images_calls": 0,
            "fallbacks": 0,
        }
    
    def _get_provider(self, provider_name: str) -> BaseProvider:
        """Get or create provider instance."""
        if provider_name not in self._providers:
            self._providers[provider_name] = get_provider(
                provider_name,
                **self.provider_kwargs
            )
        return self._providers[provider_name]
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatResponse | AsyncIterator[StreamChunk]:
        """Execute chat completion with fallback.
        
        Args:
            messages: Chat messages
            model: Model name (uses config if not provided)
            stream: Whether to stream response
            **kwargs: Additional parameters
            
        Returns:
            Chat response or stream
        """
        self._stats["chat_calls"] += 1
        
        # Determine models to try
        primary_model = model or self.chat_config.get("primary", "gpt-4o-mini")
        fallback_models = self.chat_config.get("fallbacks", [])
        models = [primary_model] + fallback_models
        
        request = ChatRequest(
            messages=messages,
            model=primary_model,
            stream=stream,
            **kwargs
        )
        
        last_error = None
        for idx, model_name in enumerate(models):
            if idx > 0:
                self._stats["fallbacks"] += 1
                logger.warning(f"Falling back to model: {model_name}")
            
            try:
                # Detect provider from model name
                provider_name = self._detect_provider(model_name)
                provider = self._get_provider(provider_name)
                
                # Update request model
                request.model = model_name
                
                # Execute
                if stream:
                    return provider.chat_stream(request, **kwargs)
                else:
                    return await provider.chat_complete(request, **kwargs)
            
            except Exception as e:
                last_error = e
                logger.error(f"Model {model_name} failed: {e}")
                continue
        
        raise ProviderError(f"All models failed. Last error: {last_error}")
    
    async def embed(
        self,
        texts: list[str] | str,
        model: str | None = None,
        **kwargs
    ) -> EmbeddingResponse:
        """Create embeddings.
        
        Args:
            texts: Text(s) to embed
            model: Embedding model
            **kwargs: Additional parameters
            
        Returns:
            Embedding response
        """
        self._stats["embeddings_calls"] += 1
        
        if isinstance(texts, str):
            texts = [texts]
        
        model = model or self.embeddings_config.get(
            "primary",
            "text-embedding-3-small"
        )
        
        request = EmbeddingRequest(texts=texts, model=model)
        
        provider_name = self._detect_provider(model)
        provider = self._get_provider(provider_name)
        
        return await provider.create_embeddings(request, **kwargs)
    
    async def generate_image(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs
    ) -> ImageResponse:
        """Generate images from prompt.
        
        Args:
            prompt: Image description
            model: Image model
            **kwargs: Additional parameters
            
        Returns:
            Generated images
        """
        self._stats["images_calls"] += 1
        
        model = model or self.images_config.get("primary", "dall-e-3")
        
        request = ImageRequest(prompt=prompt, model=model, **kwargs)
        
        provider_name = self._detect_provider(model)
        provider = self._get_provider(provider_name)
        
        return await provider.generate_images(request, **kwargs)
    
    def _detect_provider(self, model: str) -> str:
        """Detect provider from model name."""
        model_lower = model.lower()
        
        if "gpt" in model_lower or "dall-e" in model_lower or "embedding" in model_lower:
            return "openai"
        elif "claude" in model_lower:
            return "anthropic"
        elif "gemini" in model_lower or "vertex" in model_lower:
            return "google"
        elif "command" in model_lower or "embed" in model_lower:
            return "cohere"
        else:
            return "openai"  # Default
    
    def get_stats(self) -> dict[str, int]:
        """Get router statistics."""
        return self._stats.copy()
```

## 6. Adding a New Provider: Google Vertex AI

**File: `providers/google/__init__.py`**

```python
"""Google Vertex AI provider."""

from .provider import GoogleProvider

__all__ = ['GoogleProvider']
```

**File: `providers/google/provider.py`**

```python
"""Google Vertex AI provider implementation."""

from typing import Any, AsyncIterator

from ..base import BaseProvider
from ...capabilities.chat import ChatCapability
from ...capabilities.embeddings import EmbeddingsCapability
from ...types.chat import ChatRequest, ChatResponse, StreamChunk
from ...types.embeddings import EmbeddingRequest, EmbeddingResponse


class GoogleProvider(BaseProvider, ChatCapability, EmbeddingsCapability):
    """Google Vertex AI provider.
    
    Supports:
    - Chat: Gemini models
    - Embeddings: Text embeddings
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Lazy import Google SDK
        self._client = None
    
    def get_provider_name(self) -> str:
        return "google"
    
    def _ensure_client(self):
        """Lazy-load Google SDK."""
        if self._client is None:
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel
                
                # Initialize Vertex AI
                project_id = self.config.get("project_id")
                location = self.config.get("location", "us-central1")
                
                vertexai.init(project=project_id, location=location)
                self._client = GenerativeModel
            except ImportError:
                raise ImportError(
                    "google-cloud-aiplatform required for Google provider. "
                    "Install with: pip install google-cloud-aiplatform"
                )
    
    async def chat_complete(
        self,
        request: ChatRequest,
        **kwargs: Any
    ) -> ChatResponse:
        """Chat completion using Gemini."""
        self._ensure_client()
        
        # Convert our format to Gemini format
        model = self._client(request.model)
        
        # Convert messages
        gemini_messages = self._convert_messages(request.messages)
        
        # Generate
        response = await model.generate_content_async(
            gemini_messages,
            generation_config=self._build_generation_config(request, kwargs)
        )
        
        # Convert back to our format
        return self._convert_response(response, request.model)
    
    async def chat_stream(
        self,
        request: ChatRequest,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Streaming chat completion."""
        self._ensure_client()
        
        model = self._client(request.model)
        gemini_messages = self._convert_messages(request.messages)
        
        async for chunk in model.generate_content_async(
            gemini_messages,
            generation_config=self._build_generation_config(request, kwargs),
            stream=True
        ):
            yield self._convert_chunk(chunk)
    
    def supports_chat_streaming(self, model: str) -> bool:
        return "gemini" in model.lower()
    
    def supports_tools(self, model: str) -> bool:
        return "gemini-1.5" in model.lower() or "gemini-2" in model.lower()
    
    def count_chat_tokens(
        self,
        request: ChatRequest,
        model: str
    ) -> int:
        # Google has its own token counting
        self._ensure_client()
        model_obj = self._client(model)
        
        messages = self._convert_messages(request.messages)
        return model_obj.count_tokens(messages).total_tokens
    
    async def create_embeddings(
        self,
        request: EmbeddingRequest,
        **kwargs: Any
    ) -> EmbeddingResponse:
        """Create embeddings using Vertex AI."""
        self._ensure_client()
        
        from vertexai.language_models import TextEmbeddingModel
        
        model = TextEmbeddingModel.from_pretrained(request.model)
        
        embeddings = []
        for idx, text in enumerate(request.texts):
            result = await model.get_embeddings_async([text])
            embeddings.append({
                "index": idx,
                "embedding": result[0].values,
                "object": "embedding"
            })
        
        return EmbeddingResponse(
            object="list",
            data=embeddings,
            model=request.model,
            usage={"prompt_tokens": 0, "total_tokens": 0}  # Google doesn't provide this
        )
    
    def get_embedding_dimensions(self, model: str) -> int:
        if "gecko" in model.lower():
            return 768
        return 768  # Default
    
    def get_max_batch_size(self, model: str) -> int:
        return 100
    
    def count_embedding_tokens(
        self,
        texts: list[str],
        model: str
    ) -> int:
        # Approximate
        return sum(len(text.split()) for text in texts)
    
    def _convert_messages(self, messages: list[dict]) -> list:
        """Convert our message format to Gemini format."""
        # Implementation details...
        return messages
    
    def _build_generation_config(self, request: ChatRequest, kwargs: dict) -> dict:
        """Build Gemini generation config."""
        return {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
            **kwargs
        }
    
    def _convert_response(self, response: Any, model: str) -> ChatResponse:
        """Convert Gemini response to our format."""
        # Implementation details...
        pass
    
    def _convert_chunk(self, chunk: Any) -> StreamChunk:
        """Convert Gemini stream chunk to our format."""
        # Implementation details...
        pass
```

**Register the provider:**

```python
# In providers/__init__.py, add to _register_builtin_providers():

try:
    from .google import GoogleProvider
    _registry.register("google", GoogleProvider, ["vertex", "gemini"])
except ImportError:
    pass
```

## 7. Usage Examples

### Basic Chat (Existing Interface)

```python
from good_agent.llm_client import UnifiedRouter

router = UnifiedRouter(
    chat_config={
        "primary": "gpt-4o-mini",
        "fallbacks": ["gpt-3.5-turbo"]
    },
    api_key="sk-..."
)

# Chat completion
response = await router.chat(
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.choices[0].message.content)
```

### Embeddings

```python
# Single text
response = await router.embed("Hello world")
vector = response.data[0].embedding

# Batch
response = await router.embed([
    "First document",
    "Second document",
    "Third document"
])
vectors = [e.embedding for e in response.data]
```

### Image Generation

```python
response = await router.generate_image(
    prompt="A serene mountain landscape at sunset",
    model="dall-e-3",
    size="1024x1024",
    quality="hd"
)

image_url = response.data[0].url
```

### Multi-Provider with Different Capabilities

```python
router = UnifiedRouter(
    chat_config={
        "primary": "gpt-4o",           # OpenAI for chat
        "fallbacks": ["claude-3.5-sonnet"]
    },
    embeddings_config={
        "primary": "text-embedding-3-large"  # OpenAI for embeddings
    },
    images_config={
        "primary": "dall-e-3"          # OpenAI for images
    },
    api_key="sk-..."
)

# All capabilities available
chat_response = await router.chat(messages)
embeddings = await router.embed(texts)
images = await router.generate_image(prompt)
```

### Custom Provider Registration

```python
from good_agent.llm_client.providers import register_provider, BaseProvider
from good_agent.llm_client.capabilities.chat import ChatCapability

class MyCustomProvider(BaseProvider, ChatCapability):
    def get_provider_name(self) -> str:
        return "custom"
    
    async def chat_complete(self, request, **kwargs):
        # Your implementation
        pass
    
    # ... other required methods

# Register
register_provider("custom", MyCustomProvider)

# Use
router = UnifiedRouter(
    chat_config={"primary": "custom-model"},
    api_key="..."
)
```

## 8. Extension Points

### Middleware System

**File: `middleware/base.py`**

```python
"""Middleware protocol for request/response transformation."""

from typing import Protocol, Any, Callable, Awaitable


class Middleware(Protocol):
    """Middleware for transforming requests and responses."""
    
    async def before_request(
        self,
        capability: str,
        request: Any,
        **kwargs
    ) -> tuple[Any, dict]:
        """Transform request before sending to provider.
        
        Returns:
            (modified_request, modified_kwargs)
        """
        ...
    
    async def after_response(
        self,
        capability: str,
        request: Any,
        response: Any
    ) -> Any:
        """Transform response after receiving from provider.
        
        Returns:
            modified_response
        """
        ...
    
    async def on_error(
        self,
        capability: str,
        request: Any,
        error: Exception
    ) -> Exception:
        """Handle errors.
        
        Returns:
            modified_error (or re-raise)
        """
        ...
```

### Example: Caching Middleware

```python
# middleware/caching.py

import hashlib
import json
from typing import Any

class CachingMiddleware:
    """Cache responses to reduce API calls."""
    
    def __init__(self, cache_backend):
        self.cache = cache_backend
    
    async def before_request(self, capability: str, request: Any, **kwargs):
        # Check cache
        cache_key = self._make_key(capability, request, kwargs)
        cached = await self.cache.get(cache_key)
        
        if cached:
            # Return cached response (skip provider call)
            return None, {"_cached": cached}
        
        return request, kwargs
    
    async def after_response(self, capability: str, request: Any, response: Any):
        # Store in cache
        cache_key = self._make_key(capability, request, {})
        await self.cache.set(cache_key, response, ttl=3600)
        return response
    
    def _make_key(self, capability: str, request: Any, kwargs: dict) -> str:
        data = {
            "capability": capability,
            "request": request.dict() if hasattr(request, "dict") else str(request),
            "kwargs": kwargs
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
```

## Summary

This extensible architecture provides:

1. **Easy Provider Addition** - Implement capability protocols, register provider
2. **New Capabilities** - Define protocol, implement in providers
3. **Plugin System** - Runtime registration without modifying core
4. **Type Safety** - Full typing with runtime checks
5. **Lazy Loading** - Import only what's used
6. **Middleware** - Transform requests/responses
7. **Multi-Capability** - Single router for all capabilities
8. **Fallback Support** - Per-capability fallback configuration

**Key Benefits:**
- Add Google Vertex: 1 file, ~200 lines
- Add embeddings to existing provider: Implement protocol (~100 lines)
- No core modifications needed
- Maintains <200ms import time through lazy loading
