from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SupportsString(Protocol):
    """Protocol for objects that can be converted to a string"""

    def __str__(self) -> str:
        """Return the string representation of the object"""
        ...


@runtime_checkable
class SupportsLLM(Protocol):
    """Protocol for objects that can be used as LLM input"""

    def __llm__(self) -> str:
        """Return the string representation for LLM input"""
        ...


@runtime_checkable
class SupportsDisplay(Protocol):
    """Protocol for objects that can be rendered for display/UI"""

    def __display__(self) -> str:
        """Return the string representation for display purposes"""
        ...


@runtime_checkable
class SupportsRender(Protocol):
    """Protocol for objects that can be rendered with a template"""

    def render(self, **kwargs: Any) -> str:
        """Render the object using provided keyword arguments"""
        ...
