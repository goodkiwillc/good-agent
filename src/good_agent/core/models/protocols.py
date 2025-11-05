from typing import (
    ContextManager,
    Protocol,
    Self,
    runtime_checkable,
)


@runtime_checkable
class SupportsContextConfig(Protocol):
    def config(
        self,
        **kwargs,
    ) -> ContextManager[Self]: ...
