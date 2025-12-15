from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel

from good_agent.content import ContentPartType, TemplateContentPart
from good_agent.core.components import MessageInjectorComponent
from good_agent.core.models import Renderable
from good_agent.tools import tool

if TYPE_CHECKING:
    from good_agent import Agent


class ToDoItem(BaseModel):
    item: str
    complete: bool = False


class ToDoList(Renderable):
    __template__ = """
    {% if name %}
    # To-Do List: {{ name }}
    {% else %}
    # To-Do List
    {% endif %}
    {% if items %}
    {% for item in items %}
    - [{{ 'x' if item.complete else ' ' }}] {{ item.item }}
    {% endfor %}
    {% else %}
    _No items in the to-do list._
    {% endif %}
    """
    name: str
    items: list[ToDoItem]


class TaskManager(MessageInjectorComponent):
    lists: dict[str, ToDoList] = {}

    def __init__(self, *args, **kwargs):
        self.lists = {}
        super().__init__(*args, **kwargs)

    def create_list(self, name: str | None = None, items: list[str] | None = None) -> ToDoList:
        """Create a new to-do list with an optional name."""
        name = name or f"List {len(self.lists) + 1}"
        self.lists[name] = ToDoList(name=name, items=[ToDoItem(item=i) for i in (items or [])])
        return self.lists[name]

    def add_item(self, list_name: str, item: str) -> str:
        """Add a new item to the specified to-do list."""
        if list_name not in self.lists:
            raise ValueError(f"List {list_name} does not exist.")
        self.lists[list_name].items.append(ToDoItem(item=item))
        return f'Item "{item}" added to list {list_name}.'

    def complete_item(
        self,
        list_name: str,
        item_index: int | None = None,
        item_text: str | None = None,
    ) -> str:
        """Mark an item in the specified to-do list as complete. Item index is zero-based."""
        if item_index is None and item_text is None:
            raise ValueError("Either item_index or item_text must be provided.")
        if item_index is not None and item_text is not None:
            raise ValueError("Only one of item_index or item_text should be provided.")

        if item_index is None:
            for idx, todo_item in enumerate(self.lists[list_name].items):
                if todo_item.item == item_text:
                    item_index = idx
                    break
            if item_index is None:
                raise ValueError(f'Item with text "{item_text}" not found in list {list_name}.')

        if list_name not in self.lists:
            raise ValueError(f"List ID {list_name} does not exist.")
        if item_index < 0 or item_index >= len(self.lists[list_name].items):
            raise IndexError(f"Item index {item_index} is out of range for list {list_name}.")
        self.lists[list_name].items[item_index].complete = True
        return f"`{self.lists[list_name].items[item_index].item}` marked as complete."

    def view_list(self, list_name: str) -> ToDoList:
        """View the contents of the specified to-do list."""
        if list_name not in self.lists:
            raise ValueError(f"List ID {list_name} does not exist.")
        return self.lists[list_name]

    @tool(name="create_list")  # type: ignore[arg-type]
    def create_list_tool(self, name: str | None = None, items: list[str] | None = None) -> ToDoList:
        """Tool wrapper for create_list."""
        return self.create_list(name=name, items=items)

    @tool(name="add_item")  # type: ignore[arg-type]
    def add_item_tool(self, list_name: str, item: str) -> str:
        """Tool wrapper for add_item."""
        return self.add_item(list_name=list_name, item=item)

    @tool(name="complete_item")  # type: ignore[arg-type]
    def complete_item_tool(
        self,
        list_name: str,
        item_index: int | None = None,
        item_text: str | None = None,
    ) -> str:
        """Tool wrapper for complete_item."""
        return self.complete_item(list_name=list_name, item_index=item_index, item_text=item_text)

    @tool(name="view_list")  # type: ignore[arg-type]
    def view_list_tool(self, list_name: str) -> ToDoList:
        """Tool wrapper for view_list."""
        return self.view_list(list_name)

    def get_system_prompt_suffix(self, agent: Agent) -> Sequence[ContentPartType]:
        if not self.lists:
            return []

        agent.context["todo_lists"] = self.lists

        parts = [
            TemplateContentPart(
                template="""
                !# section todo
                {% for name, todo_list in todo_lists.items() %}
                    ## {{ todo_list.name }}
                    {% if todo_list.items %}
                    {% for item in todo_list.items %}
                    - [{{ 'x' if item.complete else ' ' }}] {{ item.item }}
                    {% endfor %}
                    {% else %}
                    _No items in this list._
                    {% endif %}
                {% endfor %}
                !# end section
                """,
            )
        ]

        return parts
