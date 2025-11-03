"""
CONTEXT: Custom type definitions and validation utilities for the GoodIntel platform.
ROLE: Provides type-safe, validated data structures with Pydantic integration for consistent data handling across the platform.
DEPENDENCIES:
  - good_common.types: Base type utilities and validation primitives
  - pydantic: Data validation and serialization framework
  - uuid_utils: UUID v7 implementation for time-based identifiers
  - datetime: Standard library date/time handling
ARCHITECTURE:
  - Base types: Identifier, StringDict for foundational data structures
  - Date/time types: ParsedDate, ParsedDateTime with validation and null handling
  - Functional types: FuncRef for runtime function resolution
  - Web types: RequestMethod for HTTP operation specification
  - JSON types: JSONData for flexible data interchange
KEY EXPORTS: Identifier, UUID, ParsedDate, ParsedDateTime, FuncRef, JSONData, RequestMethod
USAGE PATTERNS:
  1. Pydantic model field definitions with automatic validation
  2. Type-safe identifier handling with URL-based structure
  3. Date/time parsing with configurable formats and null handling
  4. Function reference storage and runtime resolution
  5. JSON data interchange with recursive type safety
RELATED MODULES:
  - goodintel_core.models: Base model classes using these types
  - goodintel_core.serializers: Data serialization utilities
  - goodintel_core.validation: Input validation frameworks
  - goodintel_core.clients: External API data handling

PERFORMANCE CHARACTERISTICS:
  - Validation occurs at model creation/assignment time
  - UUID v7 provides time-ordered identifiers with good collision resistance
  - Date parsing optimized for specific format patterns
  - JSON data uses Python's native typing system for runtime validation

VALIDATION STRATEGY:
  - Pydantic BeforeValidator hooks for custom parsing logic
  - Strict type checking with informative error messages
  - Null handling with explicit nullable type variants
  - URL validation and normalization for identifiers

EXTENSION POINTS:
  - Custom validation functions can be added via Pydantic validators
  - Additional date formats supported by modifying validation functions
  - UUID versions can be extended by subclassing the UUID class
  - Custom functional reference resolution patterns supported
"""

from good_common.types import (
    UPPER_CASE_STRING,
    URL,
    UUID,  # UUID v7-compatible implementation
    VALID_ZIP_CODE,
    DateTimeField,
    Domain,
    StringDictField,
    UUIDField,
)

from ._base import Identifier, StringDict
from ._dates import (
    NullableParsedDate,
    NullableParsedDateTime,
    ParsedDate,
    ParsedDateTime,
)
from ._functional import FuncRef
from ._json import JSONData
from ._web import RequestMethod

__all__ = [
    "URL",
    "StringDict",
    "Identifier",
    "UUID",
    "JSONData",
    "StringDictField",
    "UUIDField",
    "FuncRef",
    "DateTimeField",
    "ParsedDate",
    "ParsedDateTime",
    # "ParsedDateRequestMethod",
    "NullableParsedDate",
    "NullableParsedDateTime",
    "Domain",
    "VALID_ZIP_CODE",
    "UPPER_CASE_STRING",
    "RequestMethod",
]
