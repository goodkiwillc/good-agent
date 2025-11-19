import typer
from good_agent.cli.prompts import register_commands as register_prompt_commands
from good_agent.cli.run import run_agent
from good_agent.cli.serve import serve_agent

app = typer.Typer(help="Good Agent CLI")

# Register sub-commands
register_prompt_commands(app)

@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def run(
    ctx: typer.Context,
    agent_path: str = typer.Argument(..., help="Path to the agent (e.g. module:agent_instance)"),
    model: str = typer.Option(None, "--model", "-m", help="Override agent model"),
    temperature: float = typer.Option(None, "--temperature", "-t", help="Override agent temperature"),
):
    """
    Run an agent interactively in the terminal.
    Pass extra arguments to the agent factory by appending them to the command.
    """
    # Parse extra args
    extra_args = ctx.args
    run_agent(agent_path, model=model, temperature=temperature, extra_args=extra_args)

@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
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
