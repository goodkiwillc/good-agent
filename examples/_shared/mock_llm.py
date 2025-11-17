"""Miniature LanguageModel adapter for runnable examples."""

from __future__ import annotations

from typing import Sequence

from good_agent.model.llm import LanguageModel
from good_agent.mock import MockQueuedLanguageModel, MockResponse, mock_message


def assistant_response(text: str) -> MockResponse:
    """Convenience helper that wraps ``mock_message`` for assistant replies."""

    return mock_message(text, role="assistant")


class ExampleLanguageModel(LanguageModel):
    """LanguageModel subclass that replays queued mock responses.

    This adapter lets examples run without touching a real LLM while still
    exercising the normal Agent/component wiring. Responses are supplied up
    front and consumed in order each time ``complete`` (or ``stream``) is
    invoked.
    """

    def __init__(self, responses: Sequence[MockResponse | str] | None = None):
        super().__init__(model="mock-example")
        self._queue = MockQueuedLanguageModel(
            [_ensure_response(resp) for resp in responses or []],
            agent=None,
        )

    def setup(self, agent):  # type: ignore[override]
        super().setup(agent)
        self._queue.agent = agent

    def prime(self, *responses: MockResponse | str) -> None:
        """Replace the queued responses (used by tests/examples)."""

        self._queue.responses = [_ensure_response(resp) for resp in responses]
        self._queue.response_index = 0

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        if self._queue.response_index >= len(self._queue.responses):
            fallback = "Mock response"
            if messages:
                last = messages[-1]
                fallback = f"Mock reply to: {last.get('content', '')}"  # type: ignore[arg-type]
            self._queue.responses.append(assistant_response(fallback))
        return await self._queue.complete(messages, **kwargs)

    async def extract(self, messages, response_model, **kwargs):  # type: ignore[override]
        return await self._queue.extract(messages, response_model, **kwargs)

    async def stream(self, messages, **kwargs):  # type: ignore[override]
        async for chunk in self._queue.stream(messages, **kwargs):
            yield chunk


def _ensure_response(payload: MockResponse | str) -> MockResponse:
    if isinstance(payload, MockResponse):
        return payload
    return assistant_response(payload)


__all__ = ["ExampleLanguageModel", "assistant_response"]
