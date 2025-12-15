from __future__ import annotations

import asyncio
from typing import Literal

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from good_agent.agent.core import Agent
from good_agent.cli.utils import load_agent_from_path
from good_agent.messages import AssistantMessage, Message, ToolMessage

OutputFormatType = Literal["rich", "plain", "json"]


def _print_rich(console: Console, message: Message) -> None:
    """Print message using Rich formatting."""
    if isinstance(message, ToolMessage):
        tool_name = message.name or "Tool"
        content = str(message.content)
        if len(content) > 500:
            content = f"{content[:500]}... [truncated]"
        console.print(
            Panel(
                Text(content, style="dim"),
                title=f"[bold blue]Tool Output: {tool_name}[/bold blue]",
                border_style="blue",
                expand=False,
            )
        )
    elif isinstance(message, AssistantMessage):
        if message.tool_calls:
            for tool_call in message.tool_calls:
                args = tool_call.function.arguments
                console.print(
                    Panel(
                        Text(f"{args}", style="cyan"),
                        title=f"[bold cyan]Calling: {tool_call.function.name}[/bold cyan]",
                        border_style="cyan",
                        expand=False,
                    )
                )
        if message.content:
            console.print(Markdown(str(message.content)))
            console.print()


def _print_plain(message: Message) -> None:
    """Print message using plain text format."""
    import sys
    from datetime import datetime

    ts = datetime.now().strftime("%H:%M:%S")

    if isinstance(message, ToolMessage):
        tool_name = message.name or "Tool"
        content = str(message.content)[:200]
        print(f"[{ts}] TOOL_RESULT: {tool_name} | {content}", file=sys.stdout)
    elif isinstance(message, AssistantMessage):
        if message.tool_calls:
            for tool_call in message.tool_calls:
                print(
                    f"[{ts}] TOOL_CALL: {tool_call.function.name} | {tool_call.function.arguments}",
                    file=sys.stdout,
                )
        if message.content:
            print(f"[{ts}] ASSISTANT: {message.content}", file=sys.stdout)


def _print_json(message: Message) -> None:
    """Print message as JSON line."""
    import json
    import sys
    from datetime import datetime

    ts = datetime.now().isoformat()

    if isinstance(message, ToolMessage):
        output = {
            "timestamp": ts,
            "type": "tool_result",
            "tool_name": message.name or "unknown",
            "content": str(message.content),
        }
        print(json.dumps(output), file=sys.stdout)
    elif isinstance(message, AssistantMessage):
        if message.tool_calls:
            for tool_call in message.tool_calls:
                output = {
                    "timestamp": ts,
                    "type": "tool_call",
                    "tool_name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                }
                print(json.dumps(output), file=sys.stdout)
        if message.content:
            output = {
                "timestamp": ts,
                "type": "assistant",
                "content": str(message.content),
            }
            print(json.dumps(output), file=sys.stdout)


async def run_interactive_loop(
    agent: Agent,
    output_format: OutputFormatType = "rich",
):
    """Run the interactive CLI loop for a given agent."""
    console = Console()
    history = InMemoryHistory()
    session: PromptSession[str] = PromptSession(history=history)
    style = Style.from_dict({"prompt": "#ansigreen bold"})

    agent_display_name = agent.name or "Unnamed"

    # Welcome message based on format
    if output_format == "rich":
        console.print(
            Panel(
                (
                    "Started interactive session with agent: "
                    f"[bold cyan]{agent_display_name}[/bold cyan] ({agent.id})"
                ),
                title="Good Agent CLI",
                border_style="green",
            )
        )
        console.print("[dim]Type 'exit' or 'quit' to end session.[/dim]\n")
    elif output_format == "plain":
        print(f"[SESSION] Agent: {agent_display_name} ({agent.id})")
        print("[SESSION] Type 'exit' or 'quit' to end session.")
    else:  # json
        import json

        print(
            json.dumps(
                {
                    "type": "session_start",
                    "agent_name": agent_display_name,
                    "agent_id": agent.id,
                }
            )
        )

    while True:
        try:
            # Prompt handling
            if output_format == "rich":
                user_input = await session.prompt_async(
                    HTML("<prompt>➜ </prompt>"),
                    style=style,
                )
            else:
                # Plain/JSON: simple input
                user_input = await session.prompt_async("> ")

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit"}:
                if output_format == "rich":
                    console.print("[yellow]Goodbye![/yellow]")
                elif output_format == "plain":
                    print("[SESSION] Goodbye!")
                else:
                    import json

                    print(json.dumps({"type": "session_end"}))
                break

            if user_input.lower() == "clear":
                if output_format == "rich":
                    console.clear()
                continue

            if output_format == "rich":
                console.print()

            try:
                async for message in agent.execute(user_input):
                    if output_format == "rich":
                        _print_rich(console, message)
                    elif output_format == "plain":
                        _print_plain(message)
                    else:
                        _print_json(message)

            except Exception as e:
                if output_format == "rich":
                    console.print(f"[bold red]Error during execution:[/bold red] {e}")
                    import traceback

                    console.print(traceback.format_exc())
                elif output_format == "plain":
                    print(f"[ERROR] {e}")
                else:
                    import json

                    print(json.dumps({"type": "error", "message": str(e)}))

        except KeyboardInterrupt:
            continue
        except EOFError:
            break


def run_agent(
    agent_path: str,
    model: str | None = None,
    temperature: float | None = None,
    extra_args: list[str] | None = None,
    output_format: OutputFormatType = "rich",
) -> None:
    """Load and run an agent interactively."""
    try:
        agent_obj, _ = load_agent_from_path(agent_path)
    except Exception as e:
        print(f"Error loading agent: {e}")
        return

    # Instantiate if factory
    if not isinstance(agent_obj, Agent):
        if callable(agent_obj):
            try:
                # Only pass extra args if it's a factory
                # We can improve this by inspecting the signature or passing args if provided
                if extra_args:
                    agent_obj = agent_obj(*extra_args)
                else:
                    agent_obj = agent_obj()
            except Exception as e:
                print(f"Error instantiating agent factory: {e}")
                return

        if not isinstance(agent_obj, Agent):
            agent_type = type(agent_obj).__name__
            print(
                f"Error: The object at '{agent_path}' is not an Agent instance (got {agent_type})."
            )
            return

    # Apply runtime configuration overrides
    overrides: dict[str, float | str] = {}
    if model:
        overrides["model"] = model
    if temperature is not None:
        overrides["temperature"] = temperature

    if overrides:
        try:
            agent_obj.config.update(overrides)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: unable to apply overrides {overrides}: {exc}")

    # Run the async loop
    try:
        asyncio.run(run_interactive_loop(agent_obj, output_format=output_format))
    except KeyboardInterrupt:
        print("\nGoodbye!")
