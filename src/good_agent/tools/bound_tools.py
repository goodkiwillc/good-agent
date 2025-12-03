from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Generic,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

if TYPE_CHECKING:
    from good_agent.core.components.component import AgentComponent
    from good_agent.tools.tools import Tool, ToolMetadata, ToolResponse, ToolSignature

T = TypeVar("T")
P = ParamSpec("P")
FuncResp = TypeVar("FuncResp")
# NOTE:
# BoundTool is used for methods on both AgentComponent subclasses AND other
# classes (e.g., StatefulResource). Do not constrain the instance type here.
ComponentSelf = TypeVar("ComponentSelf")


class BoundTool(Generic[ComponentSelf, P, FuncResp]):
    """
    A bound Tool instance that maintains connection to its parent component.

    This class acts as a descriptor that returns a Tool instance bound to the
    component instance, allowing tool methods to be actual Tool instances while
    maintaining access to component state.

    TYPING NOTES (keep in sync with tools.tool overloads):
    - ComponentSelf is intentionally unconstrained. Tool-decorated methods can live
      on AgentComponent subclasses or other classes like StatefulResource.
    - __get__ overloads use type[Any] for owner and object for instance to prevent
      Never inference when accessed on non-Component classes. If you narrow these
      types, mypy may infer Never and surface errors like duplicated `self` or
      "expected Never" for actual arguments.
    - When binding the method, we cast the bound method to Callable[P, FuncResp]
      because the descriptor has consumed `self`. Do not remove this cast unless you
      also update the Tool typing and tests accordingly.
    """

    def __init__(
        self,
        tool_class: type[Tool],
        unbound_method: Callable[Concatenate[ComponentSelf, P], FuncResp],
        metadata: ToolMetadata,
        config: dict[str, Any],
    ):
        """
        Initialize a BoundTool descriptor.

        Args:
            tool_class: The Tool class to instantiate
            unbound_method: The unbound method from the class
            metadata: Tool metadata (name, description, etc.)
            config: Tool configuration (retry, hide, etc.)
        """
        self.tool_class = tool_class
        self.unbound_method = unbound_method
        self.metadata = metadata
        self.config = config
        self._bound_instances: dict[int, Tool[P, FuncResp]] = {}  # Cache by component instance id

        # Store original signature for reference
        self._original_sig = inspect.signature(unbound_method)

        # For type checking: create signature without 'self'
        params = list(self._original_sig.parameters.values())
        if params and params[0].name == "self":
            params = params[1:]
        # This signature is what external code sees
        self.__signature__ = self._original_sig.replace(parameters=params)

    # Expose Tool properties for type checking
    @property
    def name(self) -> str:
        """Get the tool name."""
        return self.metadata.name

    @property
    def description(self) -> str:
        """Get the tool description."""
        return self.metadata.description

    @property
    def signature(self) -> ToolSignature:
        """Get the tool signature (provided by Tool instance when accessed)."""
        # This will only be called on an instance, not the descriptor
        # The actual Tool instance will provide this
        raise AttributeError("signature is only available on Tool instances")

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> ToolResponse[FuncResp]:
        """Make the descriptor callable for type checking purposes."""
        # This should never actually be called on the descriptor itself
        # It's here for type checking when the descriptor is accessed
        raise TypeError(
            "BoundTool descriptor cannot be called directly. Access it from a component instance."
        )

    @overload
    def __get__(
        self, instance: None, owner: type[Any]
    ) -> BoundTool[ComponentSelf, P, FuncResp]: ...

    @overload
    def __get__(self, instance: ComponentSelf, owner: type[Any]) -> Tool[P, FuncResp]: ...

    def __get__(
        self,
        instance: ComponentSelf | None,
        owner: type[Any],
    ) -> Tool[P, FuncResp] | BoundTool[ComponentSelf, P, FuncResp]:
        """
        Get a Tool instance bound to the component instance.

        When accessed from a class, returns self (the descriptor).
        When accessed from an instance, returns a Tool bound to that instance.
        """
        if instance is None:
            # Accessed from class, return the descriptor itself
            return self

        # Get or create a Tool instance bound to this component instance
        instance_id = id(instance)

        if instance_id not in self._bound_instances:
            # Create a bound method for this instance
            bound_method = self.unbound_method.__get__(instance, type(instance))

            # Help type checkers: bound_method no longer has the 'self' parameter
            typed_bound_method = cast("Callable[P, FuncResp]", bound_method)

            # Import Tool here to avoid circular import
            from good_agent.tools.tools import Tool

            # Create a Tool instance with the bound method
            tool_instance = Tool(
                fn=typed_bound_method,
                name=self.metadata.name,
                description=self.metadata.description,
                retry=self.config.get("retry", False),
                hide=self.config.get("hide", []),
                **{k: v for k, v in self.config.items() if k not in ["retry", "hide"]},
            )

            # Store the component reference in the tool
            tool_instance._component = instance  # type: ignore[attr-defined]

            # Cache the tool instance
            self._bound_instances[instance_id] = tool_instance

        return cast("Tool[P, FuncResp]", self._bound_instances[instance_id])

    def __set__(self, instance: AgentComponent, value: Any) -> None:
        """Prevent setting the attribute."""
        raise AttributeError(f"Cannot set tool attribute '{self.metadata.name}'")

    def __delete__(self, instance: AgentComponent) -> None:
        """Clean up cached Tool instance when component is deleted."""
        instance_id = id(instance)
        if instance_id in self._bound_instances:
            del self._bound_instances[instance_id]

    def __repr__(self) -> str:
        """String representation of the BoundTool."""
        return f"<BoundTool '{self.metadata.name}' of {self.unbound_method.__qualname__}>"


def create_component_tool_decorator():
    """
    Create a version of the @tool decorator that returns BoundTool descriptors
    for component methods.

    This is used internally by the main @tool decorator when it detects a method.
    """

    def component_tool_decorator(
        func: Callable | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        register: bool = False,
        retry: bool = False,
        hide: list[str] | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable], BoundTool] | BoundTool:
        """
        Decorator that creates a BoundTool descriptor for component methods.
        """

        def decorator(f: Callable) -> BoundTool:
            # Extract metadata
            tool_name = name or f.__name__
            tool_description = description or inspect.getdoc(f) or ""

            # Import here to avoid circular import
            from good_agent.tools.tools import Tool, ToolMetadata

            # Create metadata object
            metadata = ToolMetadata(
                name=tool_name,
                description=tool_description,
                parameters={},  # Will be filled by Tool class
                register=register,
            )

            # Create config dict
            config = {"retry": retry, "hide": hide or [], **kwargs}

            # Create and return BoundTool descriptor
            bound_tool: BoundTool[Any, Any, Any] = BoundTool(
                tool_class=Tool,
                unbound_method=f,
                metadata=metadata,
                config=config,
            )

            # Preserve the original function attributes for introspection
            bound_tool.__name__ = f.__name__  # type: ignore[attr-defined]
            bound_tool.__doc__ = f.__doc__
            bound_tool.__module__ = f.__module__
            bound_tool.__qualname__ = f.__qualname__  # type: ignore[attr-defined]

            # Mark it as a tool for the metaclass to recognize
            bound_tool._is_bound_tool = True  # type: ignore[attr-defined]

            return bound_tool

        if func is None:
            # Called with arguments: @tool(name="foo")
            return decorator
        else:
            # Called without arguments: @tool
            return decorator(func)

    return component_tool_decorator
