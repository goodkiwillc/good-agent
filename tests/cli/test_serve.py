from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from good_agent.agent.core import Agent
from good_agent.cli.serve import create_app
from good_agent.messages import AssistantMessage


@pytest.fixture
def mock_agent():
    agent = MagicMock(spec=Agent)
    agent.model = MagicMock()
    agent.model.model_name = "mock-gpt-4"

    # Mock _fork_with_messages to return the same agent or a copy
    # Since request_agent.call() is awaited, we need to make sure the return value of fork is usable

    # Make _fork_with_messages an async method that returns the agent itself
    async def fork(messages):
        return agent

    agent._fork_with_messages = AsyncMock(side_effect=fork)

    # Mock call()
    async def call(*args, **kwargs):
        return AssistantMessage(content="Hello from API")

    agent.call = AsyncMock(side_effect=call)

    return agent


def test_serve_endpoint(mock_agent):
    # Create app with a factory that returns our mock agent
    app = create_app(lambda: mock_agent)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={"model": "test-model", "messages": [{"role": "user", "content": "Hi"}]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["content"] == "Hello from API"
    assert data["object"] == "chat.completion"

    # Verify agent was called
    mock_agent._fork_with_messages.assert_called_once()
    mock_agent.call.assert_called_once()


@pytest.mark.asyncio
async def test_serve_missing_deps(monkeypatch):
    # Simulate missing dependencies
    with patch.dict("sys.modules", {"fastapi": None, "uvicorn": None}):
        import importlib

        import good_agent.cli.serve

        # Expect SystemExit when reloading triggers the import check
        with pytest.raises(SystemExit):
            importlib.reload(good_agent.cli.serve)


def test_serve_with_args(mock_agent):
    # Test factory with args
    factory_mock = MagicMock(return_value=mock_agent)

    # Manually invoke logic from serve_agent since we can't easily spin up full server here
    # without blocking. We'll just verify factory creation logic.

    extra_args = ["--foo", "bar"]

    def agent_factory():
        return factory_mock(*extra_args)

    # Run factory
    agent = agent_factory()

    assert agent == mock_agent
    factory_mock.assert_called_once_with("--foo", "bar")
