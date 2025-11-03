"""
Base provider class.

All provider implementations should inherit from BaseProvider.
"""

from abc import ABC
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderConfig:
    """Configuration for a provider."""
    
    api_key: str
    base_url: str | None = None
    timeout: float | None = None
    max_retries: int | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """
    Abstract base class for all LLM providers.
    
    Providers should:
    1. Inherit from BaseProvider
    2. Implement one or more capability protocols (ChatCapability, etc.)
    3. Set the provider_name class attribute
    4. Initialize their SDK client in __init__
    """
    
    provider_name: str = "base"
    
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        **kwargs: Any
    ):
        """
        Initialize the provider.
        
        Args:
            api_key: API key for authentication
            base_url: Optional custom base URL
            timeout: Request timeout in seconds (default: 60.0)
            max_retries: Maximum number of retries (default: 2)
            **kwargs: Additional provider-specific parameters
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout if timeout is not None else 60.0
        self.max_retries = max_retries if max_retries is not None else 2
        self.extra_params = kwargs
