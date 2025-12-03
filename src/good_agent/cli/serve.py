import sys
import time
import uuid
from collections.abc import Callable
from typing import Any

# Optional dependencies check
try:
    import uvicorn
    from fastapi import FastAPI, HTTPException
except ImportError:
    print("Error: 'fastapi' and 'uvicorn' are required for the 'serve' command.")
    print(
        "Please install them with: pip install good-agent[server] or uv pip install good-agent[server]"
    )
    sys.exit(1)

from pydantic import BaseModel

from good_agent.agent.core import Agent
from good_agent.cli.utils import load_agent_from_path
from good_agent.messages import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
)
from good_agent.messages import (
    Message as GAMessage,
)

# --- OpenAI-compatible Models ---


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = "default"
    messages: list[ChatMessage]
    temperature: float | None = None
    stream: bool = False


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionResponseChoice]
    usage: dict[str, int] | None = None


# --- Server Implementation ---


def create_app(agent_factory: Callable[[], Agent]) -> FastAPI:
    """Create a FastAPI application exposing an OpenAI-compatible chat endpoint."""
    app = FastAPI(title="Good Agent API", version="1.0.0")

    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
    async def chat_completions(request: ChatCompletionRequest):
        if request.stream:
            raise HTTPException(status_code=501, detail="Streaming not yet supported")

        # 1. Instantiate/Get Agent
        # We assume agent_factory returns an Agent instance.
        # Ideally, we want a fresh scope.
        # If it returns a fresh agent, great. If it returns a shared one, we fork it.
        base_agent = agent_factory()
        if not isinstance(base_agent, Agent):
            raise HTTPException(
                status_code=500,
                detail="Server configuration error: Factory did not return an Agent",
            )

        # 2. Convert Messages
        ga_messages: list[GAMessage] = []
        for msg in request.messages:
            if msg.role == "system":
                ga_messages.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                ga_messages.append(UserMessage(content=msg.content))
            elif msg.role == "assistant":
                # TODO: Handle tool calls in history if needed
                ga_messages.append(AssistantMessage(content=msg.content))
            elif msg.role == "tool":
                # TODO: Map tool messages correctly
                pass

        # 3. Fork Agent with History
        # Use private method _fork_with_messages to get a fresh agent with this history
        try:
            # If base_agent is fresh, we can just set messages?
            # _fork_with_messages is designed to create a new agent from an existing one with new state.
            # If the factory creates a NEW agent every time, we can just append messages.
            # But we can't be sure. Safest is to use the fork mechanism if available,
            # or just set the messages if we know it's fresh.
            # Let's try to use _fork_with_messages on the instance.
            request_agent = await base_agent._fork_with_messages(ga_messages)
        except Exception as e:
            # Fallback if _fork_with_messages fails or isn't appropriate
            # raise HTTPException(status_code=500, detail=f"Agent fork failed: {e}")

            # Alternative: If we trust the factory returned a fresh agent
            request_agent = base_agent
            # Clear existing and add new?
            # request_agent.messages.clear() # No clear method on MessageList?
            # Let's rely on _fork_with_messages as it was seen in core.py
            raise HTTPException(status_code=500, detail=f"Agent fork failed: {e}") from e

        # 4. Run Agent
        # We use call() for a single turn
        try:
            response_message = await request_agent.call()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}") from e

        # 5. Format Response
        content = str(response_message.content) if response_message.content else ""

        choice = ChatCompletionResponseChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content),
            finish_reason="stop",
        )

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(time.time()),
            model=request.model or base_agent.config.model,
            choices=[choice],
            # usage=... # TODO: extract usage
        )

    return app


def serve_agent(
    agent_path: str,
    host: str = "127.0.0.1",
    port: int = 8000,
    extra_args: list[str] | None = None,
):
    """
    Serve an agent as an OpenAI-compatible API.
    """
    # Load agent definition
    try:
        agent_obj, _ = load_agent_from_path(agent_path)
    except Exception as e:
        print(f"Error loading agent: {e}")
        return

    # Prepare factory
    if isinstance(agent_obj, Agent):
        # It's an instance. We'll use it as a template to fork from.

        def agent_factory() -> Agent:
            return agent_obj

    elif callable(agent_obj):
        # It's a factory (class or function)
        # If extra_args are provided, we need to pass them to the factory
        if extra_args:

            def agent_factory() -> Agent:
                return agent_obj(*extra_args)

        else:

            def agent_factory() -> Agent:
                return agent_obj()
    else:
        print(f"Error: The object at '{agent_path}' is not an Agent instance or factory.")
        return

    # Create App
    app = create_app(agent_factory)

    print(f"🚀 Serving agent '{agent_path}' on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
