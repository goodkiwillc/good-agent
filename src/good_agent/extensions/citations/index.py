from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from good_agent.core.indexing import Index
from good_agent.core.models import Renderable
from good_agent.core.types import URL

# if TYPE_CHECKING:
# from ..interfaces import SupportsDisplay, SupportsLLM, SupportsRender, SupportsString

# type Renderable = SupportsDisplay | SupportsLLM | SupportsRender | SupportsString | str


class CitationIndex(Index[URL, int, Renderable]):
    """Deduplicated URL↔index registry backing ``CitationManager``."""

    def __init__(self, index_offset: int = 1):
        """
        Initialize CitationIndex with optional offset.

        Args:
            index_offset: Starting index (1-based by default for human readability)
        """
        # Configuration
        self.index_offset = index_offset

        # Internal storage
        self.url_to_index: dict[str, int] = {}
        self.index_to_url: dict[int, URL] = {}
        self.index_to_value: dict[int, Renderable | None] = {}  # Store values by index
        self.aliases: dict[str, str] = {}
        self.metadata_store: dict[str, dict[str, Any]] = {}
        self.tags_store: dict[str, set[str]] = {}
        self.next_index = index_offset

    def _to_url(self, value: URL | str, fallback: URL | str | None = None) -> URL:
        """Convert arbitrary input into a URL, falling back when conversion fails."""

        if isinstance(value, URL):
            return value

        try:
            return URL(value)
        except ValueError:
            if fallback is not None:
                if isinstance(fallback, URL):
                    return fallback
                return URL(fallback)
            raise

    def _get_canonical_url(self, url_or_key: URL | str) -> str:
        """
        Get canonical URL string from URL object or string.

        Args:
            url_or_key: URL object or string to canonicalize

        Returns:
            Canonical URL string
        """
        if not isinstance(url_or_key, URL):
            try:
                url_obj = URL(url_or_key)
            except (ValueError, Exception):
                # If URL construction fails, use string as-is
                return str(url_or_key)
        else:
            url_obj = url_or_key

        try:
            return str(url_obj.canonicalize())
        except (ValueError, Exception):
            # If canonicalization fails, use string representation
            return str(url_obj)

    def add(
        self,
        key: URL | str,
        value: Renderable | None = None,
        *,
        tags: str | list[str] | None = None,
        **metadata,
    ) -> int:
        """
        Add a URL to the index, return its global index.

        If the URL already exists (after canonicalization), returns the existing index.
        This provides automatic deduplication.

        Args:
            key: URL to add to the index
            value: Optional renderable value to store with the citation
            tags: Optional tags for the citation (string or list of strings)
            **metadata: Additional metadata for the citation

        Returns:
            Global index (1-based) for the URL

        Example:
            >>> index = CitationIndex()
            >>> idx = index.add(
            ...     "https://example.com/page",
            ...     value="Page content",
            ...     tags=["research", "example"],
            ...     title="Example Page",
            ... )
            >>> idx
            1
        """
        key = URL(key)

        canonical_url = self._get_canonical_url(key)

        # Check if URL already exists
        if canonical_url in self.url_to_index:
            existing_index = self.url_to_index[canonical_url]
            # Update value if provided
            if value is not None:
                self.index_to_value[existing_index] = value
            # Update metadata/tags if provided
            if metadata:
                self._update_metadata(canonical_url, metadata)
            if tags:
                self._update_tags(canonical_url, tags)
            return existing_index

        # Add new URL
        current_index = self.next_index
        self.url_to_index[canonical_url] = current_index
        self.index_to_url[current_index] = URL(canonical_url)
        self.index_to_value[current_index] = value  # Store the value

        # Add metadata and tags
        if metadata:
            self.metadata_store[canonical_url] = metadata.copy()
        if tags:
            self.tags_store[canonical_url] = set(tags) if isinstance(tags, list) else {tags}

        self.next_index += 1
        return current_index

    def lookup(self, key: URL | str) -> int | None:
        """
        Get global index for a URL.

        Args:
            url: URL to look up

        Returns:
            Global index if found, None otherwise

        Example:
            >>> index = CitationIndex()
            >>> index.add("https://example.com")
            1
            >>> index.lookup("https://example.com")
            1
            >>> index.lookup("https://nonexistent.com")
            None
        """
        key = URL(key)
        canonical_url = self._get_canonical_url(key)
        # Check aliases first
        if canonical := self.url_to_index.get(self._resolve_aliases_str(canonical_url)):
            return canonical
        return None

    def get_url(self, index: int) -> URL | None:
        """
        Get URL for a global index.

        Args:
            index: Global index to look up

        Returns:
            URL if found, None otherwise

        Example:
            >>> index = CitationIndex()
            >>> index.add("https://example.com")
            1
            >>> index.get_url(1)
            URL("https://example.com")
            >>> index.get_url(999)
            None
        """
        return self.index_to_url.get(index)

    def get_value(self, ref: URL | str | int) -> Renderable | None:
        """
        Get the stored value for a citation by URL or index reference.

        Args:
            ref: URL or citation index to get value for

        Returns:
            Renderable value if found, None otherwise

        Example:
            >>> index = CitationIndex()
            >>> idx = index.add("https://example.com", value="Content")
            >>> index.get_value(idx)
            "Content"
            >>> index.get_value("https://example.com")
            "Content"
        """
        if isinstance(ref, int):
            # Direct lookup by index
            return self.index_to_value.get(ref)
        else:
            ref = URL(ref)
            # Lookup by URL - first get the index
            canonical_url = self._get_canonical_url(ref)
            canonical_url = self._resolve_aliases_str(canonical_url)
            index = self.url_to_index.get(canonical_url)
            if index is not None:
                return self.index_to_value.get(index)
            return None

    def add_alias(self, url: URL | str, alias: URL | str) -> int:
        """
        Add URL alias/redirect mapping.

        This allows different URLs to resolve to the same citation index.
        Useful for handling redirects, different protocols (http/https), etc.

        Args:
            url: Primary URL (must already exist in index)
            alias: Alias URL that should resolve to the same index

        Returns:
            Global index that both URLs now resolve to

        Raises:
            ValueError: If primary URL doesn't exist in index

        Example:
            >>> index = CitationIndex()
            >>> idx = index.add("https://example.com")
            >>> index.add_alias("https://example.com", "http://example.com")
            1
            >>> index.lookup("http://example.com")
            1
        """
        url = URL(url)
        alias = URL(alias)

        # Get canonical forms of both URLs
        primary_canonical = self._get_canonical_url(url)
        alias_canonical = self._get_canonical_url(alias)

        # Primary URL must exist
        if primary_canonical not in self.url_to_index:
            raise ValueError(f"Primary URL {url} not found in index")

        # Add alias mapping
        self.aliases[alias_canonical] = primary_canonical
        return self.url_to_index[primary_canonical]

    def merge(self, local_citations: list[URL | str]) -> dict[int, int]:
        """
        Merge local citations into global index.

        Takes a list of citations from a message (with local 1-based indices)
        and ensures they exist in the global index, returning the mapping
        from local to global indices.

        Args:
            local_citations: List of URLs from a message's citations field

        Returns:
            Dictionary mapping local index (1-based) to global index

        Example:
            >>> index = CitationIndex()
            >>> # Message has citations: ["https://a.com", "https://b.com"]
            >>> mapping = index.merge(["https://a.com", "https://b.com"])
            >>> mapping
            {1: 1, 2: 2}  # Local index -> Global index
        """

        local_citations = [URL(url) if not isinstance(url, URL) else url for url in local_citations]

        mapping = {}

        for local_idx, url in enumerate(local_citations, 1):  # 1-based local indexing
            global_idx = self.add(url)  # Add to global index (or get existing)
            mapping[local_idx] = global_idx

        return mapping

    def get_metadata(self, ref: URL | int) -> dict[str, Any]:
        """
        Get metadata for a URL or citation index.

        Args:
            ref: URL or citation index to get metadata for

        Returns:
            Metadata dictionary (empty if no metadata)
        """
        if isinstance(ref, int):
            # Handle int reference (citation index)
            if ref not in self.index_to_url:
                return {}
            url = self.index_to_url[ref]
        else:
            ref = URL(ref)
            # Handle URL reference
            url = ref

        canonical_url = self._get_canonical_url(url)
        canonical_url = self._resolve_aliases_str(canonical_url)
        return self.metadata_store.get(canonical_url, {}).copy()

    def get_tags(self, ref: URL | str | int) -> set[str]:
        """
        Get tags for a URL or citation index.

        Args:
            ref: URL or citation index to get tags for

        Returns:
            Set of tags (empty if no tags)
        """
        if isinstance(ref, int):
            # Handle int reference (citation index)
            if ref not in self.index_to_url:
                return set()
            url = self.index_to_url[ref]
        else:
            # Handle URL reference
            ref = URL(ref)
            url = ref

        canonical_url = self._get_canonical_url(url)
        canonical_url = self._resolve_aliases_str(canonical_url)
        return self.tags_store.get(canonical_url, set()).copy()

    def find_by_tag(self, tag: str) -> list[int]:
        """
        Find all citations with a specific tag (required by Index protocol).

        Args:
            tag: Tag to search for

        Returns:
            List of citation indices
        """
        results = []
        for canonical_url, tags in self.tags_store.items():
            if tag in tags:
                index = self.url_to_index[canonical_url]
                results.append(index)
        return results

    def items(self) -> Iterator[tuple[int, URL]]:
        """
        Iterate over all (index, URL) pairs.

        Returns:
            Iterator yielding (index, URL) tuples
        """
        yield from self.index_to_url.items()

    def urls(self) -> Iterator[URL]:
        """
        Iterate over all URLs in the index.

        Returns:
            Iterator yielding URLs
        """
        yield from self.index_to_url.values()

    def indices(self) -> Iterator[int]:
        """
        Iterate over all indices in the index.

        Returns:
            Iterator yielding indices
        """
        yield from self.index_to_url.keys()

    def __getitem__(self, ref: int) -> URL:
        """Get URL by index (required by Index protocol)."""
        if ref not in self.index_to_url:
            raise KeyError(f"Citation index {ref} not found")
        return self.index_to_url[ref]

    def __len__(self) -> int:
        """Return the number of citations in the index."""
        return len(self.index_to_url)

    def __contains__(self, key: URL) -> bool:
        """Check if a URL exists in the index."""
        canonical_url = self._get_canonical_url(key)
        canonical_url = self._resolve_aliases_str(canonical_url)
        return canonical_url in self.url_to_index

    def _resolve_aliases(self, key: URL | str) -> URL:
        """
        Resolve URL aliases to primary URL (required by Index protocol).

        Follows the alias chain until reaching a primary URL.

        Args:
            key: URL to resolve

        Returns:
            Primary URL (may be the same if no alias)
        """
        canonical_url = self._get_canonical_url(key)
        seen = set()
        current = canonical_url

        while current in self.aliases:
            if current in seen:
                # Circular alias - break and return current
                break
            seen.add(current)
            current = self.aliases[current]

        return self._to_url(current, fallback=key)

    def _resolve_aliases_str(self, canonical_url: str) -> str:
        """
        Internal method to resolve canonical URL strings to primary URL strings.

        This is the internal string-based version used by other methods.

        Args:
            canonical_url: Canonicalized URL string to resolve

        Returns:
            Primary URL string (may be the same if no alias)
        """
        seen = set()
        current = canonical_url

        while current in self.aliases:
            if current in seen:
                # Circular alias - break and return current
                break
            seen.add(current)
            current = self.aliases[current]

        return current

    def _update_metadata(self, canonical_url: str, metadata: dict[str, Any]) -> None:
        """Update metadata for a URL."""
        if canonical_url not in self.metadata_store:
            self.metadata_store[canonical_url] = {}
        self.metadata_store[canonical_url].update(metadata)

    def _update_tags(self, canonical_url: str, tags: str | list[str]) -> None:
        """Update tags for a URL."""
        if canonical_url not in self.tags_store:
            self.tags_store[canonical_url] = set()
        if isinstance(tags, str):
            self.tags_store[canonical_url].add(tags)
        else:
            self.tags_store[canonical_url].update(tags)

    def as_dict(self) -> dict[int, URL]:
        """
        Return the index as a dictionary (required by Index protocol).

        Returns:
            Dictionary mapping reference (int) to key (URL)
        """
        return self.index_to_url.copy()

    def contents(self) -> Iterator[tuple[URL, Renderable | None]]:
        """
        Iterate over all (key, value) pairs (required by Index protocol).

        Returns:
            Iterator yielding (URL, value) tuples
        """
        for _canonical_url, index in self.url_to_index.items():
            url = self.index_to_url[index]
            value = self.index_to_value.get(index)
            yield url, value

    def contents_as_dict(self) -> dict[URL, Renderable | None]:
        """
        Return contents as a dictionary (required by Index protocol).

        Returns:
            Dictionary mapping URL to value (or None if no value stored)
        """
        result = {}
        for _canonical_url, index in self.url_to_index.items():
            url = self.index_to_url[index]
            value = self.index_to_value.get(index)
            result[url] = value
        return result

    def _get_aliases(self, key: URL | str) -> set[URL]:
        """
        Get all aliases for a given URL (required by Index protocol).

        Args:
            key: URL to get aliases for

        Returns:
            Set of alias URLs
        """
        canonical_url = self._get_canonical_url(key)
        canonical_url = self._resolve_aliases_str(canonical_url)

        # Find all aliases that point to this canonical URL
        aliases = set()
        for alias_url, target_url in self.aliases.items():
            if target_url == canonical_url:
                try:
                    aliases.add(URL(alias_url))
                except ValueError:
                    pass  # Skip invalid URLs

        return aliases

    def add_tag(self, ref: int, tag: str | list[str]) -> None:
        """
        Add tag(s) to a citation by its index reference (required by Index protocol).

        Args:
            ref: Citation index
            tag: Tag or list of tags to add
        """
        if ref not in self.index_to_url:
            raise KeyError(f"Citation index {ref} not found")

        url = self.index_to_url[ref]
        canonical_url = self._get_canonical_url(url)
        self._update_tags(canonical_url, tag)

    def remove_tag(self, ref: int, tag: str | list[str]) -> None:
        """
        Remove tag(s) from a citation by its index reference (required by Index protocol).

        Args:
            ref: Citation index
            tag: Tag or list of tags to remove
        """
        if ref not in self.index_to_url:
            raise KeyError(f"Citation index {ref} not found")

        url = self.index_to_url[ref]
        canonical_url = self._get_canonical_url(url)

        if canonical_url in self.tags_store:
            tags_to_remove = {tag} if isinstance(tag, str) else set(tag)
            self.tags_store[canonical_url] -= tags_to_remove

            # Clean up empty tag sets
            if not self.tags_store[canonical_url]:
                del self.tags_store[canonical_url]

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> list[int]:
        """
        Find citations by multiple tags (required by Index protocol).

        Args:
            tags: List of tags to search for
            match_all: If True, require all tags; if False, match any tag

        Returns:
            List of citation indices
        """
        results = []
        tags_set = set(tags)

        for canonical_url, url_tags in self.tags_store.items():
            if match_all:
                # Require all tags to be present
                if tags_set.issubset(url_tags):
                    results.append(self.url_to_index[canonical_url])
            else:
                # Match any tag
                if tags_set & url_tags:  # Set intersection
                    results.append(self.url_to_index[canonical_url])

        return results

    def set_metadata(self, ref: int, **metadata) -> None:
        """
        Set metadata for a citation by its index reference (required by Index protocol).

        Replaces all existing metadata.

        Args:
            ref: Citation index
            **metadata: Metadata key-value pairs
        """
        if ref not in self.index_to_url:
            raise KeyError(f"Citation index {ref} not found")

        url = self.index_to_url[ref]
        canonical_url = self._get_canonical_url(url)
        self.metadata_store[canonical_url] = metadata.copy()

    def update_metadata(self, ref: int, **metadata) -> None:
        """
        Update metadata for a citation by its index reference (required by Index protocol).

        Merges with existing metadata.

        Args:
            ref: Citation index
            **metadata: Metadata key-value pairs to update
        """
        if ref not in self.index_to_url:
            raise KeyError(f"Citation index {ref} not found")

        url = self.index_to_url[ref]
        canonical_url = self._get_canonical_url(url)
        self._update_metadata(canonical_url, metadata)

    def find_by_metadata(self, **criteria) -> list[int]:
        """
        Find citations by metadata criteria (required by Index protocol).

        Args:
            **criteria: Metadata key-value pairs to match

        Returns:
            List of citation indices that match all criteria
        """
        results = []

        for canonical_url, metadata in self.metadata_store.items():
            # Check if all criteria match
            if all(key in metadata and metadata[key] == value for key, value in criteria.items()):
                index = self.url_to_index[canonical_url]
                results.append(index)

        return results

    def get_entry(self, ref: int) -> tuple[URL, Renderable | None, dict[str, Any]]:
        """
        Get complete entry information for a citation (required by Index protocol).

        Args:
            ref: Citation index

        Returns:
            Tuple of (URL, value, metadata)

        Raises:
            KeyError: If citation index not found
        """
        if ref not in self.index_to_url:
            raise KeyError(f"Citation index {ref} not found")

        url = self.index_to_url[ref]
        value = self.index_to_value.get(ref)
        metadata = self.get_metadata(ref)

        return (url, value, metadata)

    def get_entries_by_tag(
        self, tag: str
    ) -> Iterator[tuple[int, URL, Renderable | None, dict[str, Any]]]:
        """
        Get all entries with a specific tag (required by Index protocol).

        Args:
            tag: Tag to search for

        Yields:
            Tuples of (index, URL, value, metadata) for each matching citation
        """
        indices = self.find_by_tag(tag)

        for index in indices:
            url = self.index_to_url[index]
            value = self.index_to_value.get(index)
            metadata = self.get_metadata(index)
            yield (index, url, value, metadata)
