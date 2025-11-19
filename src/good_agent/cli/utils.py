import importlib
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Tuple, Union

from good_agent.agent.core import Agent


def load_agent_from_path(
    path_str: str,
) -> Tuple[Union[Agent, Callable[..., Agent]], Dict[str, Any]]:
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

    if ":" not in path_str:
        raise ValueError(
            f"Invalid agent path format '{path_str}'. Expected 'module:object'."
        )

    module_path, object_name = path_str.split(":", 1)

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_path}': {e}")

    try:
        agent = getattr(module, object_name)
    except AttributeError:
        raise AttributeError(f"Module '{module_path}' has no attribute '{object_name}'")

    return agent, {}
