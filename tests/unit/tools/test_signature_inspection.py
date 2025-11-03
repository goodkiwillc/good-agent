#!/usr/bin/env python3

import inspect

from good_agent.extensions.search import AgentSearch


def test_signature_inspection():
    """Test how inspect.signature handles bound methods."""

    # Create a component instance
    search_component = AgentSearch()

    # Get the unbound method
    unbound_method = AgentSearch.search
    print(f"Unbound method signature: {inspect.signature(unbound_method)}")
    print(
        f"Unbound method params: {list(inspect.signature(unbound_method).parameters.keys())}"
    )

    # Get the bound method
    bound_method = search_component.search
    print(f"Bound method signature: {inspect.signature(bound_method)}")
    print(
        f"Bound method params: {list(inspect.signature(bound_method).parameters.keys())}"
    )

    # Check the descriptor
    bound_tool_descriptor = AgentSearch.__dict__["search"]
    print(f"BoundTool descriptor signature: {bound_tool_descriptor.__signature__}")
    print(
        f"BoundTool descriptor params: {list(bound_tool_descriptor.__signature__.parameters.keys())}"
    )


if __name__ == "__main__":
    test_signature_inspection()
