"""Smoke tests that execute every example script without emitting warnings."""

from __future__ import annotations

import asyncio
import importlib.util
import types
import warnings
from pathlib import Path

import pytest

EXAMPLES_ROOT = Path(__file__).resolve().parent.parent / "examples"


def _is_runtime_example(path: Path) -> bool:
    if path.name == "__init__.py":
        return False
    relative_parts = path.relative_to(EXAMPLES_ROOT).parts
    return not any(part.startswith("_") for part in relative_parts)


EXAMPLE_FILES = sorted(path for path in EXAMPLES_ROOT.rglob("*.py") if _is_runtime_example(path))


def _load_module(path: Path) -> types.ModuleType:
    relative = path.relative_to(EXAMPLES_ROOT)
    module_name = "examples." + ".".join(relative.with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
        raise ImportError(f"Unable to load example module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.llm  # Opt-in: requires API keys and makes real LLM calls
@pytest.mark.parametrize(
    "script_path",
    EXAMPLE_FILES,
    ids=lambda path: str(path.relative_to(EXAMPLES_ROOT)),
)
def test_example_main_runs_without_deprecations(script_path: Path) -> None:
    module = _load_module(script_path)
    if not hasattr(module, "main"):
        raise AssertionError(f"{script_path} must define a main() entry point")

    runner = module.main

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        # Ignore known third-party deprecation warnings
        warnings.filterwarnings(
            "ignore",
            message="enable_cleanup_closed ignored",
            category=DeprecationWarning,
        )
        if asyncio.iscoroutinefunction(runner):
            asyncio.run(runner())
        else:
            runner()
