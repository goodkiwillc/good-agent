from abc import ABC
from typing import TYPE_CHECKING, Protocol, TypeVar

from good_common.modeling import TypeInfo
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined


class classproperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.func(owner)

    # Optional: make it read-only
    def __set__(self, instance, value):
        raise AttributeError("can't set attribute")


if TYPE_CHECKING:

    class BaseModelLike(Protocol):
        @classproperty
        def model_fields(self) -> dict[str, FieldInfo]: ...
        @classproperty
        def model_computed_fields(self) -> dict[str, TypeInfo]: ...

        def model_dump(self) -> dict: ...

else:

    class BaseModelLike:
        pass


class ModelAllFields(BaseModelLike, ABC):
    @classmethod
    def model_all_fields(cls) -> dict[str, TypeInfo]:
        model_fields = {}
        for key, field_info in cls.model_fields.items():  # type: ignore[attr-defined]
            type_info = TypeInfo(
                field_info.annotation,
                (not field_info.is_required) and field_info.default is PydanticUndefined,
                metadata=field_info.metadata,
            )
            model_fields[key] = type_info
        computed_fields = {}
        for key, field_info in cls.model_computed_fields.items():
            type_info = TypeInfo.annotation_extract_primary_type(annotation=field_info.return_type)
            computed_fields[key] = type_info

        return {**model_fields, **computed_fields}


T = TypeVar("T", bound=BaseModel)


class Convertible(BaseModel, ABC):
    """
    Mixin class for models that can be converted to another model.
    """

    def to(
        self,
        cls: type[T],
        exclude: set | None = None,
        exclude_none: bool = True,
        **data,
    ) -> T:
        exclude = exclude or set()

        if cls.model_config.get("extra", "") != "allow":
            exclude |= set(type(self).model_fields.keys()) - set(cls.model_fields.keys())
        _data = (
            self.model_dump(
                exclude=exclude,
                exclude_none=exclude_none,
            )
            | data
        )
        return cls(
            **_data,
        )
