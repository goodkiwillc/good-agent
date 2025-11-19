from __future__ import annotations

import asyncio

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
from good_agent.messages import AssistantMessage, ToolMessage


async def run_interactive_loop(agent: Agent):
    """Run the interactive CLI loop for a given agent."""

    console = Console()
    history = InMemoryHistory()
    session: PromptSession[str] = PromptSession(history=history)

    # Style for the prompt
    style = Style.from_dict({"prompt": "#ansigreen bold"})

    agent_display_name = agent.name or "Unnamed"
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

    while True:
        try:
            user_input = await session.prompt_async(
                HTML("<prompt>➜ </prompt>"),
                style=style,
            )

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit"}:
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == "clear":
                console.clear()
                continue

            # Run the agent
            console.print()  # Add spacing

            try:
                # We use execute() to get messages as they are generated (e.g. tool calls)
                # execute() yields AssistantMessage (content) and ToolMessage (results)
                async for message in agent.execute(user_input):
                    if isinstance(message, ToolMessage):
                        # Print tool outputs
                        tool_name = message.name or "Tool"
                        content = str(message.content)
                        # Truncate long tool outputs for display
                        if len(content) > 500:
                            content = f"{content[:500]}... [truncated]"

                        console.print(
                            Panel(
                                Text(content, style="dim"),
                                title=f"🔧 Tool Output: {tool_name}",
                                border_style="blue",
                                expand=False,
                            )
                        )

                    elif isinstance(message, AssistantMessage):
                        # If the message has tool calls, print them
                        if message.tool_calls:
                            for tool_call in message.tool_calls:
                                args = tool_call.function.arguments
                                console.print(
                                    Panel(
                                        Text(f"{args}", style="cyan"),
                                        title=f"🛠️  Calling: {tool_call.function.name}",
                                        border_style="cyan",
                                        expand=False,
                                    )
                                )

                        # If the message has content, print it as Markdown
                        if message.content:
                            console.print(Markdown(str(message.content)))
                            console.print()

            except Exception as e:
                console.print(f"[bold red]Error during execution:[/bold red] {e}")
                import traceback

                console.print(traceback.format_exc())

        except KeyboardInterrupt:
            continue
        except EOFError:
            break


def run_agent(
    agent_path: str,
    model: str | None = None,
    temperature: float | None = None,
    extra_args: list[str] | None = None,
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
                "Error: The object at "
                f"'{agent_path}' is not an Agent instance (got {agent_type})."
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
        asyncio.run(run_interactive_loop(agent_obj))
    except KeyboardInterrupt:
        print("\nGoodbye!")
