from typing import Self, TypeAlias

from good_agent.core.types import URL

StringDict: TypeAlias = dict[str, str]


class Identifier(URL):
    """Normalize resource IDs onto the ``id://`` scheme for consistent routing.

    Hostnames are lowercased, trailing slashes trimmed, and query params preserved
    so that identifiers remain comparable across systems. See
    ``examples/types/identifier.py`` for basic creation and cleaning.
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
        """Return a copy stripped of internal ``zz_*`` parameters."""

        return URL(self).update(
            query={k: v for k, v in self.query_params("flat").items() if not k.startswith("zz_")}
        )

    @property
    def domain(self) -> str:
        """Lowercase host component for quick routing keys."""
        return self.host

    def as_url(self) -> URL:
        return URL(self.update(scheme="https"))
