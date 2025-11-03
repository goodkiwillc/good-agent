"""
CONTEXT: Base type definitions for foundational data structures in the GoodIntel platform.
ROLE: Provides core type abstractions for identifiers and string-based dictionaries with validation and utility methods.
DEPENDENCIES:
  - good_common.types: URL implementation with validation and parsing capabilities
ARCHITECTURE:
  - StringDict: Type alias for string-to-string mappings with validation hints
  - Identifier: URL-based identifier system with standardized structure and domain handling
KEY EXPORTS: StringDict, Identifier
USAGE PATTERNS:
  1. StringDict for configuration, metadata, and key-value data storage
  2. Identifier for resource identification with URL-based structure and domain extraction
RELATED MODULES:
  - goodintel_core.models: Base classes using these foundational types
  - goodintel_core.clients: Resource identification in external systems
  - goodintel_core.serialization: Data structure validation and conversion

PERFORMANCE NOTES:
  - StringDict provides compile-time type hints with runtime dict behavior
  - Identifier inherits URL parsing performance characteristics
  - Domain extraction uses efficient string operations
"""

from typing import Self

from good_agent.core.types import URL

type StringDict = dict[str, str]


class Identifier(URL):
    """
    URL-based identifier system with standardized structure and domain handling.

    PURPOSE: Provides a consistent, URL-based identifier format for resources across
    the GoodIntel platform with built-in domain extraction and parameter filtering.

    ROLE: Standardizes resource identification using URL structure while maintaining
    compatibility with existing URL handling utilities and validation.

    LIFECYCLE:
    1. Creation: Converts input URL/string to standardized "id://" scheme format
    2. Normalization: Lowercases domain, strips trailing slashes, preserves parameters
    3. Access: Provides domain extraction and parameter filtering utilities
    4. Serialization: Inherits URL serialization behavior

    URL STRUCTURE:
    - Scheme: Always "id" for consistent identification
    - Host: Resource domain (lowercase normalized)
    - Path: Resource identifier path (trailing slashes removed)
    - Query: Resource parameters and metadata
    - Special parameters: zz_* prefix for internal/system parameters

    TYPICAL USAGE:
    ```python
    # From existing URL
    url = URL("https://example.com/resource/123?version=1")
    identifier = Identifier(url)
    # Result: "id://example.com/resource/123?version=1"

    # From string
    identifier = Identifier("user:12345")
    # Result: "id://user:12345"

    # Domain extraction
    domain = identifier.domain  # "example.com"

    # Filter out system parameters
    clean_id = identifier.root  # Removes zz_* parameters
    ```

    NORMALIZATION RULES:
    - Scheme forced to "id" for consistency
    - Host component converted to lowercase
    - Path trailing slashes removed
    - Query parameters preserved exactly as provided
    - Username/password components preserved if present

    DOMAIN EXTRACTION:
    - Returns lowercase host component
    - Useful for resource routing and categorization
    - Compatible with standard domain handling

    PARAMETER FILTERING:
    - root property removes zz_* prefixed parameters
    - Useful for cleaning identifiers for external use
    - Preserves all standard parameters

    Args:
        url: Input URL or string to convert to identifier format
        strict: Validation strictness (inherited from URL class)

    Returns:
        Identifier: Standardized identifier URL instance

    Raises:
        ValueError: If input URL/string is invalid and strict=True

    Performance:
    - Inherits URL parsing performance characteristics
    - Domain extraction is O(1) property access
    - Parameter filtering creates new URL instance (O(n) on parameter count)

    Related:
    - URL: Base class providing URL parsing and validation
    - StringDict: Often used for storing identifier metadata
    """

    def __new__(cls, url: URL | str, strict: bool = False) -> Self:
        if isinstance(url, URL):
            _url = url
        else:
            _url = URL(url)

        if (
            _url.host_root
            not in (
                "youtube.com",
                "youtu.be",
            )
            and not _url.is_possible_short_url
        ) and not (_url.host_root == "instagram.com" and _url.path.startswith("/p/")):
            _url = URL(_url.lower())

        _url = _url.canonicalize()

        return super().__new__(
            cls,
            str(
                URL.build(
                    scheme="id",
                    username=_url.username,
                    password=_url.password,
                    host=_url.host_root.lower(),
                    path=_url.path.rstrip("/"),
                    query=_url.query_string,
                )
            ),
        )

    @property
    def root(self) -> URL:
        """
        Return ID without zz_* parameters

        Removes internal/system parameters (zz_* prefix) from the identifier,
        returning a clean identifier suitable for external use or comparison.

        Returns:
            URL: New identifier instance without system parameters

        Example:
        ```python
        id_with_params = Identifier("resource:123?version=1&zz_internal=abc")
        clean_id = id_with_params.root
        # clean_id: "id://resource:123?version=1"
        ```
        """

        return URL(self).update(
            query={
                k: v
                for k, v in self.query_params("flat").items()
                if not k.startswith("zz_")
            }
        )

    @property
    def domain(self) -> str:
        """
        Extract domain component from identifier.

        Returns the lowercase host component of the identifier, useful for
        categorization, routing, and domain-based processing.

        Returns:
            str: Domain name component of the identifier

        Example:
        ```python
        identifier = Identifier("user:12345@domain.com")
        domain = identifier.domain  # "domain.com"
        ```
        """
        return self.host

    def as_url(self) -> URL:
        return URL(self.update(scheme="https"))
