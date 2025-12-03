from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

if TYPE_CHECKING:
    pass


KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")
RefT = TypeVar("RefT")


class Index(Protocol[KeyT, RefT, ValueT]):
    def __getitem__(self, ref: RefT) -> KeyT: ...

    def __contains__(self, KeyT) -> bool: ...

    def add(
        self,
        key: KeyT | str,
        value: ValueT | None = None,
        *,
        tags: str | list[str] | None = None,
        **metadata,
    ) -> RefT: ...

    def lookup(self, key: KeyT | str) -> RefT | None: ...

    def get_value(self, ref: RefT | KeyT | str) -> ValueT | None: ...

    def add_alias(self, key: KeyT | str, alias: KeyT | str) -> RefT: ...

    # add a key alias - i.e. alias -> primary key

    def _resolve_aliases(self, key: KeyT | str) -> KeyT: ...

    # resolve a key to its canonical form

    def _get_aliases(self, key: KeyT | str) -> set[KeyT]:
        ...
        # get any aliases for a given key

    def items(self) -> Iterator[tuple[RefT, KeyT]]: ...

    def as_dict(self) -> dict[RefT, KeyT]: ...

    def contents(self) -> Iterator[tuple[KeyT, ValueT | None]]: ...

    def contents_as_dict(self) -> dict[KeyT, ValueT | None]: ...

    # Tag Management
    def add_tag(self, ref: RefT, tag: str | list[str]) -> None: ...

    def remove_tag(self, ref: RefT, tag: str | list[str]) -> None: ...

    def get_tags(self, ref: RefT) -> set[str]: ...

    def find_by_tag(self, tag: str) -> list[RefT]: ...

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> list[RefT]: ...

    # Metadata Management
    def get_metadata(self, ref: RefT) -> dict[str, Any]: ...

    def set_metadata(self, ref: RefT, **metadata) -> None: ...

    def update_metadata(self, ref: RefT, **metadata) -> None: ...

    def find_by_metadata(self, **criteria) -> list[RefT]: ...

    # Combined Retrieval
    def get_entry(self, ref: RefT) -> tuple[KeyT, ValueT | None, dict[str, Any]]: ...

    def get_entries_by_tag(
        self, tag: str
    ) -> Iterator[tuple[RefT, KeyT, ValueT | None, dict[str, Any]]]: ...
