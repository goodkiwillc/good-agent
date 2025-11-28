"""Shared CLI utilities for mode example scripts."""

import argparse
from typing import Literal

from good_agent.agent.core import Agent
from good_agent.utilities.console import (
    JsonConsoleBackend,
    PlainConsoleBackend,
    RichConsoleBackend,
)

OutputFormat = Literal["rich", "plain", "json"]


def parse_output_format() -> OutputFormat:
    """Parse command line arguments for output format.

    Returns:
        Output format: "rich", "plain", or "json"
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain text output without styling",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON output",
    )
    args, _ = parser.parse_known_args()

    if args.json:
        return "json"
    elif args.plain:
        return "plain"
    return "rich"


def configure_console(agent: Agent, output_format: OutputFormat) -> None:
    """Configure the agent's console backend based on output format.

    Args:
        agent: Agent to configure
        output_format: Desired output format
    """
    if output_format == "plain":
        agent._console.backend = PlainConsoleBackend()
    elif output_format == "json":
        agent._console.backend = JsonConsoleBackend()
    else:
        agent._console.backend = RichConsoleBackend()
