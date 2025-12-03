import datetime
import logging
from typing import Any, ClassVar, Generic, Literal, TypeVar

import lxml.html
from good_common.utilities import now_et
from pydantic import (
    Field,
    computed_field,
)

from good_agent.core.models.base import (
    GoodBase,
)
from good_agent.core.models.renderable import Renderable
from good_agent.core.types import URL

logger = logging.getLogger(__name__)


def extract_first_level_xml(xml_string):
    """
    Extract the inner content of first-level XML-like tags from a string.

    Args:
        xml_string (str): A string containing XML-like content

    Returns:
        str: The concatenated first-level XML elements with their content
    """

    tree = lxml.html.fromstring(xml_string)

    return "".join([lxml.html.tostring(child).decode() for child in tree])


class Document(Renderable):
    # uid: UUID | None = None
    slug: str
    version: int = 1
    title: str | None = None
    content: str | None = None
    raw: bytes | None = None
    created_at: datetime.datetime = Field(default_factory=now_et)


class Report(GoodBase):
    # uid: UUID | None = None
    name: str
    slug: str
    project_slug: str | None = None
    date: datetime.date
    version: int = 1
    content: str
    created_at: datetime.datetime = Field(default_factory=now_et)
    updated_at: datetime.datetime = Field(default_factory=now_et)
    # data: dict | None = Field(default_factory=dict)
    links: list[URL] = Field(default_factory=list)
    posts: list[URL] = Field(default_factory=list)

    # user_posts: list[UserPosts] = Field(default_factory=list)


class Query(GoodBase):
    __type__: ClassVar[str] = "query"
    id: URL
    data: dict[str, Any] = Field(default_factory=dict)
    attempt: int = 0
    last_run: datetime.datetime | None = None

    @computed_field
    def type(self) -> str:
        return self.__type__


T_Results = TypeVar("T_Results")


class QueryResults(GoodBase, Generic[T_Results]):
    query: URL
    data: T_Results


def extract_inner_tags(content: str) -> str:
    logger.debug(content[:100] + "..." if len(content) > 100 else content)
    extract = extract_first_level_xml(content)
    logger.debug(extract[:100] + "..." if len(extract) > 100 else extract)
    return extract


T_Item = TypeVar("T_Item", bound=Renderable)


class IterableCollection(Renderable, Generic[T_Item]):
    # __template_filters__ = {"inner_content": extract_inner_tags}

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
        from good_agent.core.text import string

        _items = [string.unindent(item.render()) for item in self.items]
        if self.render_type == "direct":
            return _items
        elif self.render_type == "extract":
            return [extract_inner_tags(item) for item in _items]
