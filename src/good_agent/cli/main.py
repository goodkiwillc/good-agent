import typer

from good_agent.cli.config import GlobalConfig
from good_agent.cli.prompts import register_commands as register_prompt_commands
from good_agent.cli.run import run_agent
from good_agent.cli.serve import serve_agent

app = typer.Typer(help="Good Agent CLI")
config_app = typer.Typer(help="Manage global configuration")
app.add_typer(config_app, name="config")

# Register sub-commands
register_prompt_commands(app)


@app.callback()
def main(
    ctx: typer.Context,
    profile: str = typer.Option("default", "--profile", help="Configuration profile to use"),
):
    """
    Good Agent CLI - A framework for building reliable AI agents.
    """
    # Store profile in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile

    # Inject configuration into environment
    # This ensures all commands (run, serve, etc.) have access to the config
    config = GlobalConfig(profile=profile)
    config.inject_into_environ()


@config_app.command("set")
def config_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key (e.g. openai)"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """Set a configuration value."""
    profile = ctx.obj.get("profile", "default")
    config = GlobalConfig(profile=profile)
    config.set(key, value)
    typer.echo(f"Set '{key}' in profile '{profile}'")


@config_app.command("get")
def config_get(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key"),
):
    """Get a configuration value."""
    profile = ctx.obj.get("profile", "default")
    config = GlobalConfig(profile=profile)
    value = config.get(key)
    if value is None:
        typer.echo(f"Key '{key}' not set in profile '{profile}' or defaults.")
        raise typer.Exit(code=1)
    typer.echo(value)


@config_app.command("list")
def config_list(
    ctx: typer.Context,
    show_secrets: bool = typer.Option(False, "--show-secrets", help="Show full values of secrets"),
):
    """List all configuration values for the current profile."""
    profile = ctx.obj.get("profile", "default")
    config = GlobalConfig(profile=profile)
    values = config.list()

    if not values:
        typer.echo(f"No configuration set for profile '{profile}'.")
        return

    typer.echo(f"Configuration for profile '{profile}':")
    for key, value in values.items():
        display_value = str(value)
        # Mask secrets unless requested
        if not show_secrets and any(
            s in key.lower() for s in ["key", "token", "secret", "password"]
        ):
            if len(display_value) > 8:
                display_value = display_value[:4] + "..." + display_value[-4:]
            else:
                display_value = "***"

        typer.echo(f"  {key} = {display_value}")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    agent_path: str = typer.Argument(..., help="Path to the agent (e.g. module:agent_instance)"),
    model: str = typer.Option(None, "--model", "-m", help="Override agent model"),
    temperature: float = typer.Option(
        None, "--temperature", "-t", help="Override agent temperature"
    ),
    plain: bool = typer.Option(
        False, "--plain", help="Plain text output without styling (for scripts/agents)"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output (JSONL format)"
    ),
):
    """
    Run an agent interactively in the terminal.
    Pass extra arguments to the agent factory by appending them to the command.

    Output format options:
      --plain  Minimal text output, ideal for piping or agent consumption
      --json   Structured JSON lines, ideal for log aggregation
    """
    # Determine output format
    from typing import Literal

    output_format: Literal["rich", "plain", "json"] = "rich"
    if json_output:
        output_format = "json"
    elif plain:
        output_format = "plain"

    # Parse extra args
    extra_args = ctx.args
    run_agent(
        agent_path,
        model=model,
        temperature=temperature,
        extra_args=extra_args,
        output_format=output_format,
    )


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def serve(
    ctx: typer.Context,
    agent_path: str = typer.Argument(..., help="Path to the agent (e.g. module:agent_instance)"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
):
    """
    Serve an agent as an OpenAI-compatible API.
    Pass extra arguments to the agent factory by appending them to the command.
    """
    extra_args = ctx.args
    serve_agent(agent_path, host=host, port=port, extra_args=extra_args)


if __name__ == "__main__":
    app()
