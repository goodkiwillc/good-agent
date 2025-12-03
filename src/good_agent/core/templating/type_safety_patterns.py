from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

from jinja2 import TemplateSyntaxError as JinjaError

# Pattern 1: Using Protocols for Duck Typing
# --------------------------------------------
# Instead of checking hasattr(obj, 'attribute'), define a Protocol


@runtime_checkable
class Initializable(Protocol):
    """Protocol for objects that track their initialization state."""

    _initialized: bool


@runtime_checkable
class ErrorWithContext(Protocol):
    """Protocol for exceptions with error context information."""

    lineno: int | None
    name: str | None
    filename: str | None
    message: str


# Pattern 2: Using getattr with defaults
# ---------------------------------------
# Replace hasattr checks with getattr and a default value


class SingletonWithState:
    """Example of type-safe singleton pattern without hasattr."""

    _instance: SingletonWithState | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Type-safe initialization check
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._state = {}


# Pattern 3: Using try/except with specific exception types
# -----------------------------------------------------------
# For optional attributes, catch AttributeError explicitly


def process_exception_safely(e: Exception) -> dict[str, str | int | None]:
    """Process exception attributes in a type-safe manner."""
    result: dict[str, Any] = {"message": str(e)}

    # Instead of hasattr, use try/except
    try:
        result["lineno"] = e.lineno  # type: ignore[attr-defined]
    except AttributeError:
        result["lineno"] = None

    try:
        result["filename"] = e.filename  # type: ignore[attr-defined]
    except AttributeError:
        result["filename"] = None

    return result


# Pattern 4: Using Direct Type Checks for Known Types
# -----------------------------------------------------
# When dealing with known library types, check them directly


def handle_error_with_direct_check(e: Exception) -> str:
    """Handle errors using direct type checking for known types."""
    parts = [f"Error: {e}"]

    # Direct type check for known exception types
    if isinstance(e, JinjaError):
        # Type checker knows these attributes exist
        if e.lineno:
            parts.append(f"Line: {e.lineno}")
        if e.filename:
            parts.append(f"File: {e.filename}")
    elif hasattr(e, "__class__") and e.__class__.__name__ == "TemplateSyntaxError":
        # Fallback for dynamically loaded or different versions
        lineno = getattr(e, "lineno", None)
        filename = getattr(e, "filename", None)
        if lineno:
            parts.append(f"Line: {lineno}")
        if filename:
            parts.append(f"File: {filename}")

    return "\n".join(parts)


# Pattern 5: Using TypeGuards for custom type narrowing
# -------------------------------------------------------
# For Python 3.10+, use TypeGuard for even more precise typing

if TYPE_CHECKING:
    from typing import TypeGuard


def has_location_info(e: Exception) -> TypeGuard[ErrorWithContext]:
    """Type guard to check if exception has location information."""
    return isinstance(e, ErrorWithContext) and any([e.lineno, e.name, e.filename])


def process_with_typeguard(e: Exception) -> str:
    """Process exception using type guard."""
    if has_location_info(e):
        # Type checker now knows e has lineno, name, filename
        return f"Error at {e.filename}:{e.lineno}"
    return str(e)


# Pattern 6: Using Abstract Base Classes with properties
# --------------------------------------------------------
# Define expected attributes as abstract properties


class ConfigurableComponent(ABC):
    """Base class that enforces initialization pattern."""

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if component is initialized."""
        ...

    def ensure_initialized(self) -> None:
        """Ensure component is initialized before use."""
        if not self.is_initialized:
            raise RuntimeError("Component not initialized")


class ConcreteComponent(ConfigurableComponent):
    """Concrete implementation with type-safe initialization."""

    def __init__(self):
        self._initialized = False
        # ... initialization code ...
        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# Pattern 7: Using dataclasses or Pydantic for guaranteed attributes
# --------------------------------------------------------------------
# Attributes are always present and typed


@dataclass
class ErrorInfo:
    """Type-safe error information container."""

    message: str
    lineno: int | None = None
    filename: str | None = None
    name: str | None = None

    @classmethod
    def from_exception(cls, e: Exception) -> ErrorInfo:
        """Create ErrorInfo from any exception safely."""
        return cls(
            message=str(e),
            lineno=getattr(e, "lineno", None),
            filename=getattr(e, "filename", None),
            name=getattr(e, "name", None),
        )


# Pattern 8: Using __dict__ inspection with type annotations
# ------------------------------------------------------------
# When you absolutely need dynamic attribute checking


T = TypeVar("T")


def get_attribute_safely(obj: object, attr: str, default: T) -> T | str:
    """Get attribute from object with type-safe default."""
    # Use vars() or __dict__ for safer attribute access
    obj_dict = vars(obj) if hasattr(obj, "__dict__") else {}
    return obj_dict.get(attr, default)


# Summary of Patterns
# --------------------
# 1. Use Protocols for duck typing instead of hasattr
# 2. Use getattr with defaults for optional attributes
# 3. Use try/except AttributeError for truly optional attributes
# 4. Use isinstance with runtime_checkable Protocols
# 5. Use TypeGuards for custom type narrowing (Python 3.10+)
# 6. Use ABC with abstract properties for enforced attributes
# 7. Use dataclasses/Pydantic for guaranteed typed attributes
# 8. Use __dict__ inspection when dynamic checking is needed

# Each pattern has different trade-offs:
# - Protocols: Best for duck typing and third-party types
# - getattr: Simple and effective for optional attributes
# - try/except: Good for performance-critical code
# - isinstance: Best when you control the type hierarchy
# - TypeGuards: Most precise type narrowing
# - ABC: Best for enforcing contracts in inheritance
# - dataclasses: Best for data containers with known attributes
# - __dict__: Last resort for truly dynamic cases
