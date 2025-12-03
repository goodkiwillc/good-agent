from types import SimpleNamespace
from typing import cast

import pytest
from good_agent import Agent
from good_agent.extensions.task_manager import TaskManager


def test_task_manager_crud_flow():
    manager = TaskManager()
    todo = manager.create_list(name="Focus", items=["alpha"])
    assert todo.name == "Focus"
    manager.add_item("Focus", "beta")
    manager.complete_item("Focus", item_index=1)
    view = manager.view_list("Focus")
    assert view.items[1].complete is True


def test_task_manager_complete_item_by_text_and_prompt_suffix():
    manager = TaskManager()
    manager.create_list(name="Sprint", items=["code", "review"])
    manager.complete_item("Sprint", item_text="review")
    agent_stub = cast(Agent, SimpleNamespace(context={}))
    parts = manager.get_system_prompt_suffix(agent_stub)
    assert agent_stub.context["todo_lists"]["Sprint"].items[1].complete is True
    assert parts, "Should inject template content when lists exist"


def test_task_manager_complete_item_validations():
    manager = TaskManager()
    manager.create_list(name="Ops", items=["deploy"])
    with pytest.raises(ValueError):
        manager.complete_item("Ops", item_index=None, item_text=None)
    with pytest.raises(IndexError):
        manager.complete_item("Ops", item_index=5)


@pytest.mark.asyncio
async def test_task_manager_tool_wrappers_delegate_calls():
    manager = TaskManager()
    create_resp = await manager.create_list_tool(name="Backlog", items=["todo"])
    assert create_resp.response.name == "Backlog"

    add_resp = await manager.add_item_tool("Backlog", "ship")
    assert "ship" in add_resp.response

    complete_resp = await manager.complete_item_tool("Backlog", item_text="ship")
    assert "ship" in complete_resp.response

    view_resp = await manager.view_list_tool("Backlog")
    assert view_resp.response.items[-1].complete is True


def test_task_manager_view_list_missing_list():
    manager = TaskManager()
    with pytest.raises(ValueError):
        manager.view_list("unknown")
