from contextlib import AbstractContextManager
from typing import (
    Protocol,
    Self,
    runtime_checkable,
)


@runtime_checkable
class SupportsContextConfig(Protocol):
    def config(
        self,
        **kwargs,
    ) -> AbstractContextManager[Self]: ...
