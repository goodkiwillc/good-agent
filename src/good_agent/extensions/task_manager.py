from collections.abc import Sequence

from good_agent.models import Renderable

# Remove direct fetch imports - now handled by WebFetcher
# from goodintel_fetch.web import fetch, ExtractedContent
# Storage (from store module)
# External dependencies
from pydantic import BaseModel

# Core agent imports
from good_agent import (
    Agent,
    ContentPartType,
    MessageInjectorComponent,
    TemplateContentPart,
    tool,
)


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

    @tool
    def create_list(
        self, name: str | None = None, items: list[str] | None = None
    ) -> ToDoList:
        """Create a new to-do list with an optional name. Returns the ID of the new list."""
        name = name or f"List {len(self.lists) + 1}"
        self.lists[name] = ToDoList(
            name=name, items=[ToDoItem(item=i) for i in (items or [])]
        )
        return self.lists[name]

    @tool
    def add_item(self, list_name: str, item: str) -> str:
        """Add a new item to the specified to-do list."""
        if list_name not in self.lists:
            raise ValueError(f"List {list_name} does not exist.")
        self.lists[list_name].items.append(ToDoItem(item=item))
        return f'Item "{item}" added to list {list_name}.'

    @tool
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
                raise ValueError(
                    f'Item with text "{item_text}" not found in list {list_name}.'
                )

        if list_name not in self.lists:
            raise ValueError(f"List ID {list_name} does not exist.")
        if item_index < 0 or item_index >= len(self.lists[list_name].items):
            raise IndexError(
                f"Item index {item_index} is out of range for list {list_name}."
            )
        self.lists[list_name].items[item_index].complete = True
        return f"`{self.lists[list_name].items[item_index].item}` marked as complete."

    @tool
    def view_list(self, list_name: str) -> ToDoList:
        """View the contents of the specified to-do list."""
        if list_name not in self.lists:
            raise ValueError(f"List ID {list_name} does not exist.")
        return self.lists[list_name]

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
