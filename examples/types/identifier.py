"""Work with Identifier helper for normalized resource IDs."""

from __future__ import annotations

from good_agent.core.types import Identifier


def main() -> None:
    ident = Identifier("https://Example.com/path/123?version=1&zz_debug=1")
    print("identifier:", ident)
    print("domain:", ident.domain)
    print("root:", ident.root)


if __name__ == "__main__":
    main()
