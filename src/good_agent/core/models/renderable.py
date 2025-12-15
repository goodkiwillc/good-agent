import logging
from abc import ABC
from collections import ChainMap
from typing import Any, Generic, Literal, TypedDict, TypeVar

from jinja2.exceptions import TemplateError
from pydantic import BaseModel, Field

from good_agent.core.models.mixins import ModelAllFields
from good_agent.core.templating import (
    AbstractTemplate,
    create_environment,
)
from good_agent.utilities.lxml import extract_first_level_xml

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=dict[str, Any])


class TemplateFilterParams(TypedDict):
    value: Any
    template: str
    locals: dict[str, Any]


class Renderable(BaseModel, ModelAllFields, AbstractTemplate, ABC):
    """
    Renderable is a mixin class for models that can be rendered using Jinja2 templates.
    It provides a way to define templates and render them with the model's data.
    It also provides a way to define filters that can be used in the templates.

    """

    __template__ = "{{ __root__.model_dump() | yaml }}"
    _template_config_via_init_subclass: bool = False

    def __init_subclass__(cls, __template_config__: dict | None = None, **kwargs):
        """
        Handle __template_config__ passed during class definition.

        Example:
            class MyResponse(Renderable, __template_config__={"render_content": "plain"}):
                pass
        """
        super().__init_subclass__(**kwargs)

        # If __template_config__ is passed as a class parameter, store it as a class attribute
        # and mark it as set via init_subclass to avoid deprecation warning
        if __template_config__ is not None:
            cls.__template_config__ = cls.__template_config__.new_child(__template_config__)
            cls._template_config_via_init_subclass = True

    def __init__(self, *args, __template_config__: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        # Check if this class has a manually set __template_config__ as a class variable
        # We need to distinguish between:
        # 1. Config set via __init_subclass__ (allowed)
        # 2. Config inherited from AbstractTemplate (allowed)
        # 3. Config manually set as class variable (deprecated)

        # Look for a non-empty __template_config__ that wasn't set via __init_subclass__
        class_config = self.__class__.__dict__.get("__template_config__")
        has_manual_config = (
            class_config is not None
            and not isinstance(class_config, ChainMap)  # AbstractTemplate uses ChainMap
            and not getattr(self.__class__, "_template_config_via_init_subclass", False)
        )

        if has_manual_config:
            import warnings

            warnings.warn(
                "Setting __template_config__ as a class variable is deprecated. "
                "Use either the __init_subclass__ syntax (class MyClass(Renderable, __template_config__={...}):) "
                "or pass it to the constructor.",
                DeprecationWarning,
                stacklevel=2,
            )

        # Determine class-level config: prefer the current class's own layer if present.
        # If __template_config__ is a ChainMap, maps[0] corresponds to the layer defined
        # on this class (or the first inherited layer for MRO cases like mixins).
        raw_config = getattr(self.__class__, "__template_config__", {})
        if isinstance(raw_config, ChainMap):
            class_config = raw_config.maps[0] if raw_config.maps else {}
        else:
            class_config = raw_config or {}

        # Constructor config should take precedence over class config
        if __template_config__:
            self._template_config = ChainMap(__template_config__, class_config)
        else:
            self._template_config = ChainMap(class_config)

    def model_dump_render(self, **kwargs):
        from good_agent.core.text import unindent

        _all_fields = self.__class__.model_all_fields()
        _sub_models = set()
        _data = self.model_dump(**kwargs)

        for key, field in _all_fields.items():
            try:
                if field.is_sequence:
                    # handle list-types
                    if isinstance(field.item_type, type) and issubclass(
                        field.item_type.type, Renderable
                    ):
                        _sub_models.add(key)
                        _data[key] = getattr(self, key)
                    elif isinstance(field.item_type, type) and issubclass(
                        field.item_type.type, str
                    ):
                        _data[key] = [unindent(item) for item in (getattr(self, key, []) or [])]
                else:
                    if isinstance(field.item_type, type) and issubclass(
                        field.type, Renderable
                    ):  # or field.type is typing.Self:
                        _data[key] = getattr(self, key)
                        _sub_models.add(key)
                    elif str(field.type) == "str":
                        # handle string types
                        _data[key] = unindent(getattr(self, key))
            except Exception as e:
                logger.error(f"Error processing field {key} of type {field.type}: {e}")
                _data[key] = None
            try:
                if field.is_sequence:
                    # handle list-types
                    if isinstance(field.item_type, type) and issubclass(
                        field.item_type.type, Renderable
                    ):
                        _sub_models.add(key)
                        _data[key] = getattr(self, key)
                    elif isinstance(field.item_type, type) and issubclass(
                        field.item_type.type, str
                    ):
                        _data[key] = [unindent(item) for item in (getattr(self, key, []) or [])]
                else:
                    if isinstance(field.item_type, type) and issubclass(
                        field.type, Renderable
                    ):  # or field.type is typing.Self:
                        _data[key] = getattr(self, key)
                        _sub_models.add(key)
                    elif str(field.type) == "str":
                        # handle string types
                        _data[key] = unindent(getattr(self, key))
            except Exception as e:
                logger.error(f"Error processing field {key} of type {field.type}: {e}")
                _data[key] = None
        return _data

    def render(
        self,
        **config,
    ) -> str:
        from good_agent.core.text import unindent

        data = self.model_dump_render()

        data["__root__"] = self

        # Handle case where _template_config doesn't exist (for backwards compatibility)
        if not hasattr(self, "_template_config"):
            base_config = getattr(self, "__template_config__", {})
            self._template_config = ChainMap(base_config)

        data["__config__"] = self._template_config.new_child(config)

        env = create_environment()

        try:
            template = env.from_string(self.get_template())
            return unindent(template.render(data))
        except TemplateError as e:
            logger.error(
                f"""
                Error compiling template: {e}
                Class: {self.__class__.__name__}
                Template: {self.get_template()}
                """
                # f"Error rendering template: {e}\nTemplate: {self.get_template()}"
            )
            raise e
            # return repr(self)

    def __str__(self):
        return self.render()

    def __iadd__(self, other):
        if isinstance(other, str):
            return self.render() + other
        if isinstance(other, Renderable):
            return self.render() + other.render()
        return NotImplemented

    def __add__(self, other):
        if isinstance(other, str):
            return self.render() + other
        if isinstance(other, Renderable):
            return self.render() + other.render()
        return NotImplemented


T_Item = TypeVar("T_Item", bound=Renderable)


def _extract_inner_tags(content: str) -> str:
    logger.debug(content[:100] + "..." if len(content) > 100 else content)
    extract = extract_first_level_xml(content)
    logger.debug(extract[:100] + "..." if len(extract) > 100 else extract)
    return extract


class RenderableCollection(
    Renderable,
    Generic[T_Item],
    __template_config__={"render_type": "direct"},
):
    __template__ = """
    <{{collection_name}}>
    {% for item in __root__.render_items %}
        <{{item_type}} idx="{{loop.index}}">
        {{ item | indent(4) }}
        </{{item_type}}>
    {% endfor %}
    </{{collection_name}}>
    """
    collection_name: str
    item_type: str
    render_type: Literal["direct", "extract"] = "direct"
    items: list[T_Item] = Field(default_factory=list)

    @property
    def render_items(self):
        from good_agent.core.text import unindent

        _render_type = self._template_config.get("render_type", "direct")
        _items = [unindent(item.render()) for item in self.items]
        if _render_type == "direct":
            return _items
        elif _render_type == "extract":
            return [_extract_inner_tags(item) for item in _items]
