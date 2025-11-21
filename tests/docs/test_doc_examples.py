import pytest
import importlib.util
import asyncio
import sys
from pathlib import Path

# Discover all python files in examples/docs
# We use a relative path from this test file to find the examples directory
EXAMPLE_DIR = Path(__file__).parents[2] / "examples" / "docs"
EXAMPLE_FILES = list(EXAMPLE_DIR.glob("*.py"))


def get_example_id(path: Path) -> str:
    """Generate a friendly test ID from the filename."""
    return path.name


@pytest.mark.parametrize("example_file", EXAMPLE_FILES, ids=get_example_id)
@pytest.mark.asyncio
@pytest.mark.vcr
async def test_doc_example(example_file, llm_vcr):
    """
    Dynamically loads and executes the 'main' coroutine of a documentation example.
    The llm_vcr fixture automatically records/replays LLM interactions.
    """
    module_name = f"examples.docs.{example_file.stem}"

    # Create a module spec
    spec = importlib.util.spec_from_file_location(module_name, example_file)
    if spec is None or spec.loader is None:
        pytest.fail(f"Could not load spec for {example_file}")

    # Create the module
    module = importlib.util.module_from_spec(spec)

    # Add to sys.modules to handle imports correctly if needed
    sys.modules[module_name] = module

    try:
        # Execute the module
        spec.loader.exec_module(module)

        # Check for main coroutine
        if hasattr(module, "main") and asyncio.iscoroutinefunction(module.main):
            await module.main()
        else:
            pytest.fail(
                f"Example {example_file.name} must have an async main() function"
            )

    finally:
        # Clean up sys.modules
        if module_name in sys.modules:
            del sys.modules[module_name]
