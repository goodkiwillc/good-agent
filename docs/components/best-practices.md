# Best Practices

## 1. Design for Reusability

```python
class ConfigurableComponent(AgentComponent):
    """Component with flexible configuration."""

    def __init__(self, api_key: str, timeout: float = 30.0, retries: int = 3):
        super().__init__()
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries

    def _clone_init_args(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        return (), {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "retries": self.retries
        }
```

## 2. Handle Errors Gracefully

```python
class RobustComponent(AgentComponent):

    @tool
    async def reliable_operation(self, data: str) -> str:
        """Operation with comprehensive error handling."""
        try:
            if not self.enabled:
                return "Component is disabled"

            if not data.strip():
                return "Error: Empty data provided"

            result = await self._risky_operation(data)
            return f"Success: {result}"

        except ConnectionError:
            return "Error: Service unavailable, please try again later"
        except ValueError as e:
            return f"Error: Invalid data format - {e}"
        except Exception as e:
            # Log unexpected errors but don't crash
            logger.error(f"Unexpected error in {self.__class__.__name__}: {e}")
            return "Error: Internal component error"
```

## 3. Use Dependency Injection
<!-- @TODO: does this show dependency injection as we have it set up? or is this a gneeric example? DI has a specific pattern in this library -->
```python
from abc import ABC, abstractmethod

class StorageInterface(ABC):
    @abstractmethod
    async def save(self, key: str, data: dict) -> bool:
        pass

class TestableComponent(AgentComponent):
    def __init__(self, storage: StorageInterface | None = None):
        super().__init__()
        self.storage = storage or self._create_default_storage()

    def _create_default_storage(self) -> StorageInterface:
        """Create default storage implementation."""
        return FileStorage()  # Default implementation

    @tool
    async def save_data(self, key: str, data: dict) -> str:
        """Save data using injected storage."""
        success = await self.storage.save(key, data)
        return "Saved successfully" if success else "Save failed"
```

## 4. Implement Proper Logging

```python
import logging

class LoggingComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def install(self, agent: Agent):
        await super().install(agent)
        self.logger.info(f"Component installed on agent {agent.name}")

    @tool
    async def logged_operation(self, data: str) -> str:
        """Operation with comprehensive logging."""
        self.logger.debug(f"Starting operation with data: {data[:50]}...")

        try:
            result = await self._perform_operation(data)
            self.logger.info(f"Operation completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Operation failed: {e}", exc_info=True)
            raise
```

## 5. Document Component APIs

```python
class WellDocumentedComponent(AgentComponent):
    """
    A well-documented component for demonstration.

    This component provides example functionality and serves as a template
    for creating new components with proper documentation.

    Attributes:
        config (dict): Component configuration
        state (str): Current component state

    Example:
        >>> component = WellDocumentedComponent(config={"key": "value"})
        >>> agent = Agent("Assistant", extensions=[component])
        >>> await agent.initialize()
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize the component.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__()
        self.config = config or {}
        self.state = "initialized"

    @tool
    async def documented_tool(self, input_data: str, format_type: str = "json") -> str:
        """
        Process input data and return formatted result.

        This tool demonstrates proper documentation with clear parameter
        descriptions and return value documentation.

        Args:
            input_data: The data to process (required)
            format_type: Output format - "json", "xml", or "text" (default: "json")

        Returns:
            Formatted string containing the processed data

        Raises:
            ValueError: If format_type is not supported

        Example:
            The agent can call this tool like:
            "Process this data: 'hello world' in XML format"
        """
        if format_type not in ["json", "xml", "text"]:
            raise ValueError(f"Unsupported format: {format_type}")

        # Implementation details...
        return f"Processed '{input_data}' as {format_type}"
```
