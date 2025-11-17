from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from good_agent.events import AgentEvents
from good_agent.model.streaming import StreamingHandler


class FakeLitellm:
    def stream_chunk_builder(self, chunks: list[Any]) -> dict[str, Any]:
        return {"chunks": chunks}


class FakeRouter:
    async def acompletion(self, *, messages: list[Any], **config: Any) -> AsyncIterator:
        assert "parallel_tool_calls" not in config

        async def _generator() -> AsyncIterator:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta={"content": "hi"}, finish_reason=None)]
            )

        return _generator()


class FakeLanguageModel:
    def __init__(self) -> None:
        self.model = "gpt-test"
        self.fallback_models: list[str] = []
        self.router = FakeRouter()
        self.litellm = FakeLitellm()
        self.api_stream_responses: list[Any] = []
        self.api_responses: list[Any] = []
        self.api_errors: list[Any] = []
        self.last_events: list[tuple[AgentEvents, dict[str, Any]]] = []

    def _prepare_request_config(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    def _update_usage(self, _response: Any) -> None:
        pass

    def do(self, event: AgentEvents, **kwargs: Any) -> None:
        self.last_events.append((event, kwargs))


@pytest.mark.asyncio()
async def test_streaming_handler_strips_parallel_tool_calls_when_no_tools() -> None:
    llm = FakeLanguageModel()
    handler = StreamingHandler(llm)

    collected: list[str | None] = []

    async for chunk in handler.stream([], parallel_tool_calls=True):
        collected.append(chunk.content)

    assert collected == ["hi"]
    assert llm.api_stream_responses
    assert llm.api_responses and llm.api_errors == []

    before_event = llm.last_events[0]
    assert before_event[0] is AgentEvents.LLM_STREAM_BEFORE
    assert "parallel_tool_calls" not in before_event[1]["parameters"]

    after_event = llm.last_events[-1]
    assert after_event[0] is AgentEvents.LLM_STREAM_AFTER
    assert "parallel_tool_calls" not in after_event[1]["parameters"]
