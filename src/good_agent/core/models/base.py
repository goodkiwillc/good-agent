import warnings
from abc import ABC
from typing import Any, ClassVar

from good_common.utilities import int_to_base62, object_farmhash
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, TypeAdapter
from pydantic_core import PydanticUndefined

from good_agent.core.types import UUID


class PrivateAttrBase(PydanticBaseModel):
    """PURPOSE: Enable validated private attributes on Pydantic models.

    ROLE: Adds safe initialization/validation for attributes declared in
    ``__private_attributes__`` while guarding against name collisions
    with public fields.

    BEHAVIOR:
    - Warns when a public field shares a name with a private attribute (underscore prefixed)
    - Accepts private values via either underscored or plain keys at init time
    - Validates each private attribute using its annotated type via TypeAdapter
    """

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        for k in cls.model_fields:
            if f"_{k}" in cls.__private_attributes__:
                warnings.warn(
                    f"Model field `{k}` has the same name as a private attribute (with prefix).\n"
                    "This may cause unexpected behavior.",
                    stacklevel=2,
                )
        cls.__annotations__.pop("clickhouse_config", None)

    def __init__(self, /, **data: Any):
        _private_attributes = {
            k: None
            for k, v in self.__private_attributes__.items()
            if (k in data or k.lstrip("_") in data)
            or (v.default is not None or v.default_factory is not None)
        }
        _private_attribute_types = {}

        for _k in _private_attributes:
            _private_attribute_types[_k] = self.__class__.__annotations__.get(_k, Any)
            # Get the private attribute definition
            private_attr = self.__private_attributes__[_k]

            # Determine the default value
            if private_attr.default is not PydanticUndefined:
                default_value = private_attr.default
            elif private_attr.default_factory is not None:
                default_value = private_attr.default_factory()
            else:
                default_value = None

            # Try to get value from data (with or without underscore prefix)
            _private_attributes[_k] = data.pop(_k.lstrip("_"), data.pop(_k, default_value))

        # Validate each private attribute individually
        for key, type_hint in _private_attribute_types.items():
            if key in _private_attributes:
                _private_attributes[key] = TypeAdapter(type_hint).validate_python(
                    _private_attributes[key]
                )
        # logger.debug(_private_attributes)
        super().__init__(**data)

        for _k, v in _private_attributes.items():
            k = _k.lstrip("_")
            if hasattr(self, f"_validate_{k}"):
                v = getattr(self, f"_validate_{k}")(v)
            setattr(self, f"_{k}", v)


class GoodBase(PydanticBaseModel):
    """PURPOSE: Repository-wide base model with consistent config and hashing.

    ROLE: Central base for domain models. Establishes JSON/enum handling,
    attribute docstring usage, and a fast, stable object hash used for caching,
    sets/dicts, and content-addressable references.

    HASHING:
    - ``__hash__`` uses farmhash over a normalized model representation
    - ``hash`` property exposes a short base62-encoded string for logs/keys
    """

    __non_hash_fields__: ClassVar[set[str]] = set()

    model_config = ConfigDict(
        use_enum_values=True,
        # validate_default=True,
        use_attribute_docstrings=True,
        populate_by_name=True,
        ser_json_bytes="base64",
        # val_json_bytes="base64",
        ser_json_timedelta="float",
        # from_attributes=True
    )

    # @classmethod
    # def __init_subclass__(cls, **kwargs):
    #     super().__init_subclass__(**kwargs)
    #     if not hasattr(cls, "__non_hash_fields__"):
    #         cls.__non_hash_fields__ = set()

    def __hash__(self):
        return object_farmhash(self, exclude_keys=self.__non_hash_fields__)

    @property
    def hash(self):
        return int_to_base62(self.__hash__())

    # def __init__(self, **data):
    #     super().__init__(**data)


# Identifiable removed because it's not referenced anywhere - and just instantiated elsewhere


class Identifiable(GoodBase, ABC):
    """PURPOSE: Base for models that require a stable UUID primary key.

    ROLE: Extends GoodBase with an auto-generated, time-ordered UUID (v7)
    for better locality in databases and easier sorting by creation time.

    TYPICAL USAGE:
    - Extend for entities persisted in stores or referenced across systems.
    """

    model_config = ConfigDict(extra="allow")

    id: UUID = Field(default_factory=UUID.create_v7)
