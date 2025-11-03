"""
CONTEXT: UUID v7 implementation with Pydantic integration for time-ordered identifiers.
ROLE: Provides time-ordered UUID generation and validation with JSON schema support for consistent identifier management across the GoodIntel platform.
DEPENDENCIES:
  - uuid_utils: UUID v7 implementation for time-based, sortable identifiers
  - pydantic: Core schema integration and JSON schema generation
  - uuid: Standard library UUID for compatibility and fallback
ARCHITECTURE:
  - UUID class: Enhanced UUID with v7 support and custom validation
  - Schema integration: Pydantic core schema and JSON schema generation
  - Validation: Multi-format input support (string, int, bytes, UUID objects)
  - Serialization: String-based JSON serialization with format specification
KEY EXPORTS: UUID (enhanced with v7 support)
USAGE PATTERNS:
  1. Pydantic model field definitions with automatic validation
  2. Time-ordered identifier generation for database records
  3. API response formatting with proper UUID format specification
  4. Database primary keys with natural sorting by creation time
RELATED MODULES:
  - goodintel_core.models: Base models using UUID types
  - goodintel_core.serialization: Data conversion utilities
  - goodintel_core.clients: External API identifier handling
  - goodintel_core.database: Database schema definitions

UUID V7 ADVANTAGES:
  - Time-ordered: Natural sorting by creation time without separate timestamp
  - Sortable: Chronological ordering without additional sort keys
  - Collision resistant: 128-bit randomness with time component
  - K-sortable: Lexicographically sortable for distributed systems
  - Database friendly: Works well with indexed columns and ranges

VALIDATION STRATEGY:
  - Multiple input formats accepted (string hex, integer, bytes, UUID objects)
  - Strict format validation with informative error messages
  - Automatic conversion to standard UUID format
  - JSON schema generation with format specification

PERFORMANCE CHARACTERISTICS:
  - Generation is O(1) with cryptographic randomness
  - Validation optimized for common input formats
  - Serialization uses efficient string conversion
  - Memory efficient with standard UUID object structure

INSTALLATION REQUIREMENT:
  Requires uuid_utils package for UUID v7 support:
  pip install python-ulid
"""

from typing import Any, Literal, Required, Self, TypedDict
from uuid import UUID as _DEFAULT_UUID

try:
    from uuid_utils import UUID as _UUID
    from uuid_utils import uuid7
except ModuleNotFoundError as e:  # pragma: no cover
    raise RuntimeError(
        'The `ulid` module requires "uuid_utils" to be installed. '
        'You can install it with "pip install python-ulid".'
    ) from e
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticCustomError, SchemaSerializer, core_schema


class UuidSchema(TypedDict, total=False):
    type: Required[Literal["uuid"]]
    version: Literal[1, 3, 4, 5, 6, 7]
    strict: bool
    ref: str
    metadata: dict[str, Any]
    serialization: core_schema.SerSchema


class UUID(_UUID):
    def encode(self) -> str:
        return str(self)

    def __get_pydantic_json_schema__(
        self,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        field_schema = handler(core_schema)
        field_schema.pop("anyOf", None)  # remove the bytes/str union
        field_schema.update(type="string", format=f"uuid{self.uuid_version}")
        return field_schema

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        schema = core_schema.with_info_wrap_validator_function(
            cls._validate_ulid,
            core_schema.union_schema(
                [
                    core_schema.is_instance_schema(_DEFAULT_UUID),
                    core_schema.is_instance_schema(_UUID),
                    core_schema.is_instance_schema(cls),
                    core_schema.int_schema(),
                    core_schema.bytes_schema(),
                    core_schema.str_schema(),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                info_arg=False,
                return_schema=core_schema.str_schema(),
                when_used="json",
            ),
        )
        cls.__pydantic_serializer__ = SchemaSerializer(
            schema
        )  # <-- this is necessary for pydantic-core to serialize

        return schema

    @classmethod
    def _validate_ulid(
        cls,
        value: Any,
        handler: core_schema.ValidatorFunctionWrapHandler,
        info: core_schema.ValidationInfo,
    ) -> Any:
        try:
            if isinstance(value, int):
                ulid = cls(int=value)
            elif isinstance(value, str):
                ulid = cls(hex=value)
            elif isinstance(value, cls) or isinstance(value, _DEFAULT_UUID):
                ulid = cls(int=value.int)
            else:
                ulid = cls(bytes=value)
        except ValueError as e:
            raise PydanticCustomError(
                "uuid_format",
                "Unrecognized format",
            ) from e
        return handler(ulid)

    @classmethod
    def create_v7(cls) -> Self:
        return cls(int=uuid7().int)
