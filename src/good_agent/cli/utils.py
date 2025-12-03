import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from good_agent.agent.core import Agent


def load_agent_from_path(
    path_str: str,
) -> tuple[Agent | Callable[..., Agent], dict[str, Any]]:
    """
    Load an agent object or factory from a string path 'module:object'.

    Args:
        path_str: String in format 'module.submodule:variable_name'

    Returns:
        A tuple containing:
        - The object found at the path (Agent instance or factory function)
        - A dictionary of potential configuration overrides (currently empty, reserved for future use)

    Raises:
        ValueError: If path format is incorrect
        ImportError: If module cannot be imported
        AttributeError: If object cannot be found in module
    """
    # Add CWD to sys.path to allow loading local modules if not already there
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # Check for built-in aliases
    BUILT_IN_AGENTS = {
        "good-agent": "good_agent.agents.meta:agent",
        "good-agent-agent": "good_agent.agents.meta:agent",
        "research": "good_agent.agents.research:agent",
        "research-agent": "good_agent.agents.research:agent",
    }

    if path_str in BUILT_IN_AGENTS:
        path_str = BUILT_IN_AGENTS[path_str]

    if ":" not in path_str:
        raise ValueError(f"Invalid agent path format '{path_str}'. Expected 'module:object'.")

    module_path, object_name = path_str.split(":", 1)

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_path}': {e}") from e

    try:
        agent = getattr(module, object_name)
    except AttributeError as e:
        raise AttributeError(f"Module '{module_path}' has no attribute '{object_name}'") from e

    return agent, {}
