from __future__ import annotations

from copy import deepcopy
from typing import Iterable, List

from lxml import etree


class MDXLElement:
    def __init__(self, elem: etree._Element):
        self._root = elem


class MDXL:
    def __init__(self, xml: str):
        if isinstance(xml, bytes):
            self._root = etree.fromstring(xml)
        else:
            self._root = etree.fromstring(xml.encode("utf-8"))

    @property
    def outer(self) -> str:
        return etree.tostring(self._root, encoding="unicode")

    @property
    def llm_outer_text(self) -> str:
        # Concatenate all text content with newlines for readability
        return "\n".join(s.strip() for s in self._root.itertext() if s.strip())

    def select_all(self, xpath: str) -> List[MDXLElement]:
        results = self._root.xpath(xpath)
        # Filter only element nodes
        elems: Iterable[etree._Element] = [
            r for r in results if isinstance(r, etree._Element)
        ]
        return [MDXLElement(e) for e in elems]

    def select_one(self, xpath: str) -> MDXLElement | None:
        items = self.select_all(xpath)
        return items[0] if items else None

    def without(self, *xpaths: str) -> "MDXL":
        # Deep copy the tree to avoid mutating original
        root_copy = deepcopy(self._root)
        for xp in xpaths:
            matches = root_copy.xpath(xp)
            for node in list(matches):
                if isinstance(node, etree._Element):
                    parent = node.getparent()
                    if parent is not None:
                        parent.remove(node)
        new = object.__new__(MDXL)
        new._root = root_copy
        return new
