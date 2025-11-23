# `good-agent serve`

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Serve any Good Agent as an OpenAI-compatible API server. This allows you to expose your agent over HTTP, making it accessible to other applications or frontends that support the OpenAI API standard.

## Prerequisites

- Install `good-agent` with the CLI extras (`pip install good-agent[cli]`).
- Ensure your agent module is importable.

!!! note "Command synopsis"
    ```bash
    good-agent serve [OPTIONS] module.path:object_name [EXTRA_ARGS...]
    ```

## Basic Usage

To serve an agent on the default host (127.0.0.1) and port (8000):

```bash
good-agent serve examples.sales:agent
```

## Customizing Host and Port

You can specify the host and port using the `--host` and `--port` options:

```bash
good-agent serve examples.sales:agent --host 0.0.0.0 --port 8080
```

## Factory Functions

Similar to `run`, you can use factory functions to create agent instances dynamically. Arguments passed after the agent path are forwarded to the factory:

```bash
good-agent serve examples.factory:build_support_agent prod us-east --port 9000
```

## API Compatibility

The server provides endpoints compatible with the OpenAI Chat Completions API:

- `POST /v1/chat/completions`: Send messages to the agent and receive a response.
- `GET /v1/models`: List available models (returns the agent as a model).

This allows you to use standard OpenAI client libraries to interact with your served agent:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused")

response = client.chat.completions.create(
    model="examples.sales:agent",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Configuration

The `serve` command respects the global configuration managed by `good-agent config`. You can also use the `--profile` flag to load specific configuration profiles:

```bash
good-agent serve --profile prod examples.sales:agent
```
