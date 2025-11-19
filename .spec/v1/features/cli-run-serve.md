## Feature Spec: CLI Run & Serve Commands

### 1. Overview
This feature introduces two new CLI commands to `good-agent`:
- `good-agent run`: Launches an interactive chat session with a specified agent.
- `good-agent serve`: Exposes a specified agent via an OpenAI-compatible API server.

These commands enable developers to quickly test agents in the terminal and deploy them as standard APIs without writing boilerplate code.

### 2. Requirements & Constraints

#### `good-agent run`
- **Command**: `good-agent run <agent_path> [OPTIONS] [AGENT_ARGS]...`
- **Arguments**:
    - `agent_path`: Import path to the agent instance or factory function (e.g., `my_module:agent` or `path.to.file:my_agent`).
    - `AGENT_ARGS`: Optional extra arguments passed to the agent factory if `agent_path` points to a callable.
- **Options**:
    - `--model`: Override the model used by the agent.
    - `--temperature`: Override the temperature.
- **Functionality**:
    - Dynamically load the agent from the path.
    - If `agent_path` is a factory, pass `AGENT_ARGS` and any overrides to it.
    - Start an interactive REPL (Read-Eval-Print Loop) using `prompt_toolkit`.
    - Stream agent responses to stdout using `rich`.
    - Display tool usage and internal events.
    - Support basic session commands (e.g., `exit`, `clear`).
    - Maintain conversation history for the session.
- **Dependencies**: `rich`, `typer`, `prompt_toolkit` (added).
- **Note**: `agent.execute(streaming=True)` is not yet implemented, so we will use `agent.execute()` which yields messages (assistant and tool) to provide a responsive experience (showing tool execution steps).

#### `good-agent serve`
- **Command**: `good-agent serve <agent_path> --host <host> --port <port> [OPTIONS] [AGENT_ARGS]...`
- **Arguments**:
    - `agent_path`: Import path to the agent.
    - `--host`: Host to bind (default: `127.0.0.1`).
    - `--port`: Port to bind (default: `8000`).
    - `AGENT_ARGS`: Optional extra arguments passed to the agent factory.
- **Functionality**:
    - Check if `fastapi` and `uvicorn` are installed. If not, exit with a helpful error message suggesting `pip install good-agent[server]`.
    - Start a FastAPI server.
    - Expose `POST /v1/chat/completions`.
    - Map OpenAI-format JSON body to `good-agent` input.
    - Execute agent.
    - Return OpenAI-format JSON response (streaming supported via Server-Sent Events).
- **Dependencies**: `fastapi`, `uvicorn` (Optional extras).

### 3. Current Architecture Hooks
- **Agent Loading**: Will utilize Python's `importlib` to resolve string paths to Python objects.
- **Agent Execution**: Will use the standard `async with Agent(...)` context manager or existing agent instance methods.
- **CLI Entry Point**: A new `src/good_agent/cli/main.py` will be created as the central entry point, integrating `prompts.py` if needed.

### 4. API Sketches

#### CLI Entry Point (`src/good_agent/cli/main.py`)
```python
import typer
from good_agent.cli.prompts import app as prompts_app
from good_agent.cli.run import run_agent
from good_agent.cli.serve import serve_agent

app = typer.Typer()
app.add_typer(prompts_app, name="prompts")

@app.command()
def run(agent_path: str):
    run_agent(agent_path)

@app.command()
def serve(agent_path: str, host: str = "127.0.0.1", port: int = 8000):
    serve_agent(agent_path, host, port)

if __name__ == "__main__":
    app()
```

#### Dynamic Loading Utility
```python
import importlib
import sys
from pathlib import Path

def load_agent(path_str: str):
    # Add current directory to sys.path to allow loading local modules
    sys.path.insert(0, str(Path.cwd()))
    
    module_path, object_name = path_str.split(":")
    module = importlib.import_module(module_path)
    agent = getattr(module, object_name)
    return agent
```

### 5. Lifecycle & State

#### Run (Interactive)
1.  Load Agent.
2.  Initialize `Conversation` / `MessageList`.
3.  Loop:
    -   Prompt user.
    -   Add user message to history.
    -   `await agent.arun(...)` or equivalent.
    -   Print chunks/response.
    -   Add assistant message to history.

#### Serve (API)
1.  Load Agent (once at startup or per request? Per request allows statelessness if agent is designed that way, but usually agents are instantiated. If the path points to an *instance*, we use that. If *class*, we might instantiate. For now, assume it points to an *instance* or a *factory*).
    -   *Decision*: Prefer factory or fresh instance per request for full isolation, OR maintain single instance if it's stateful?
    -   *Constraint*: `good-agent` agents are typically stateful wrappers around a conversation. The API `chat/completions` is stateless (history passed in request).
    -   *Implementation*: The endpoint receives `messages`. We should instantiate a *new* agent (or use a lightweight runner) for each request, initialized with the provided messages.
    -   *Requirement*: The `agent_path` should probably point to an `Agent` class or a factory function that accepts `messages` and configuration, OR if it points to an instance, we need to be careful about shared state.
    -   *Refinement*: If it points to a configured `Agent` instance, we might need to `clone` it or update its history for the request.
    -   *Simplest Approach*: Assume `agent_path` points to an `Agent` instance. For `chat/completions`, we take the `messages` from the request, set them on the agent (replacing current history), run it, and return the result. Wait, concurrent requests on a single global agent instance would be bad (race conditions on history).
    -   *Better Approach*: `agent_path` returns a *blueprint* or *factory*. OR, we treat the agent as a definition and create a new context for each execution.
    -   *Pragmatic Approach*: Copy the configuration from the loaded agent object but create a new execution context for the request.

### 6. Testing Strategy
-   **Unit Tests**: Test the dynamic loader, the CLI command parsing.
-   **Integration Tests**:
    -   Create a dummy agent in `tests/fixtures`.
    -   Run `good-agent run` with `pexpect` or similar to verify interaction.
    -   Run `good-agent serve` in a background thread/process and hit it with `httpx`/`curl`.

### 7. Open Questions / TODOs
-   [ ] Handling dependencies: `fastapi`, `uvicorn` need to be installed. Should they be optional extras? `pip install good-agent[cli]` or `[server]`? For now, maybe just add to dev or main if acceptable.
-   [ ] Streaming response format for `serve` (SSE).
-   [ ] handling `agent_path` that requires arguments to instantiate.
