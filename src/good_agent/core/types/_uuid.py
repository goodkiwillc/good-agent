from typing import Any, ClassVar, Literal, Required, Self, TypedDict
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
    DEFAULT_SCHEMA_VERSION: ClassVar[int] = 7

    def encode(self) -> str:
        return str(self)

    @property
    def uuid_version(self) -> int:
        """Expose the UUID version for schema/tests compatibility."""
        return getattr(self, "version", self.DEFAULT_SCHEMA_VERSION)

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        field_schema = handler(core_schema)
        field_schema.pop("anyOf", None)  # remove the bytes/str union
        field_schema.update(
            type="string",
            format=f"uuid{getattr(cls, 'DEFAULT_SCHEMA_VERSION', 7)}",
        )
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
        cls.__pydantic_serializer__ = SchemaSerializer(  # type: ignore[attr-defined]
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
            elif isinstance(value, (cls, _DEFAULT_UUID)):
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
