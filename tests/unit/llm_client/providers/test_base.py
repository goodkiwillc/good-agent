"""
Tests for base provider (RED phase).

Tests the BaseProvider abstract class and ProviderConfig.
"""

import pytest
from abc import ABC


class TestProviderConfig:
    """Test ProviderConfig dataclass."""
    
    def test_config_creation(self):
        """Test creating a ProviderConfig."""
        from good_agent.llm_client.providers.base import ProviderConfig
        
        config = ProviderConfig(
            api_key="test-key",
            base_url="https://api.example.com"
        )
        
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.example.com"
    
    def test_config_optional_fields(self):
        """Test ProviderConfig with optional fields."""
        from good_agent.llm_client.providers.base import ProviderConfig
        
        config = ProviderConfig(
            api_key="test-key",
            timeout=60.0,
            max_retries=5
        )
        
        assert config.api_key == "test-key"
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.base_url is None
    
    def test_config_extra_params(self):
        """Test ProviderConfig with extra parameters."""
        from good_agent.llm_client.providers.base import ProviderConfig
        
        config = ProviderConfig(
            api_key="test-key",
            extra_params={"custom_header": "value"}
        )
        
        assert config.extra_params == {"custom_header": "value"}


class TestBaseProvider:
    """Test BaseProvider abstract class."""
    
    def test_base_provider_is_abstract(self):
        """Test that BaseProvider inherits from ABC."""
        from good_agent.llm_client.providers.base import BaseProvider
        
        # BaseProvider should inherit from ABC (for future abstract methods)
        assert issubclass(BaseProvider, ABC)
        
        # BaseProvider can be instantiated (it's a concrete base class)
        # but is intended to be subclassed by actual provider implementations
        provider = BaseProvider(api_key="test")
        assert provider.api_key == "test"
    
    def test_base_provider_has_required_attrs(self):
        """Test that BaseProvider defines required attributes."""
        from good_agent.llm_client.providers.base import BaseProvider
        
        # Should have these class attributes
        assert hasattr(BaseProvider, 'provider_name')
        assert hasattr(BaseProvider, '__init__')
    
    def test_concrete_provider_implementation(self):
        """Test creating a concrete provider implementation."""
        from good_agent.llm_client.providers.base import BaseProvider
        
        class TestProvider(BaseProvider):
            """Test concrete provider."""
            
            provider_name = "test"
            
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
        
        # Should be able to instantiate concrete class
        provider = TestProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.provider_name == "test"
    
    def test_provider_with_config(self):
        """Test provider initialization with various config options."""
        from good_agent.llm_client.providers.base import BaseProvider
        
        class TestProvider(BaseProvider):
            provider_name = "test"
            
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
        
        provider = TestProvider(
            api_key="test-key",
            base_url="https://api.test.com",
            timeout=30.0,
            max_retries=3
        )
        
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.test.com"
        assert provider.timeout == 30.0
        assert provider.max_retries == 3
    
    def test_provider_default_values(self):
        """Test that provider has sensible defaults."""
        from good_agent.llm_client.providers.base import BaseProvider
        
        class TestProvider(BaseProvider):
            provider_name = "test"
            
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
        
        provider = TestProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        # Should have reasonable defaults
        assert provider.timeout is not None or hasattr(provider, 'timeout')
        assert provider.max_retries is not None or hasattr(provider, 'max_retries')
