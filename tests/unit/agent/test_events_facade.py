from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from good_agent import Agent
from good_agent.agent.events import AgentEventsFacade
from good_agent.core.event_router import EventRouter


@pytest.fixture
def mock_agent() -> Agent:
    return cast(Agent, MagicMock(spec=Agent))


@pytest.fixture
def events_facade(mock_agent: Agent) -> AgentEventsFacade:
    return AgentEventsFacade(mock_agent)


class TestAgentEventsFacade:
    @patch("good_agent.agent.events.EventRouter")
    @pytest.mark.asyncio
    async def test_apply(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.apply_async = AsyncMock(return_value="result")
        res = await events_facade.apply("test_event", param="value")

        mock_event_router.apply_async.assert_called_once_with(
            mock_agent, "test_event", param="value"
        )
        assert res == "result"

    @patch("good_agent.agent.events.EventRouter")
    @pytest.mark.asyncio
    async def test_apply_async(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.apply_async = AsyncMock(return_value="result")
        res = await events_facade.apply_async("test_event", param="value")

        mock_event_router.apply_async.assert_called_once_with(
            mock_agent, "test_event", param="value"
        )
        assert res == "result"

    @patch("good_agent.agent.events.EventRouter")
    def test_apply_sync(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.apply_sync.return_value = "result"
        res = events_facade.apply_sync("test_event", param="value")

        mock_event_router.apply_sync.assert_called_once_with(
            mock_agent, "test_event", param="value"
        )
        assert res == "result"

    @patch("good_agent.agent.events.EventRouter")
    @pytest.mark.asyncio
    async def test_apply_typed(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.apply_typed = AsyncMock(return_value="result")
        res = await events_facade.apply_typed(
            "test_event",
            params_type=str,
            return_type=int,
            param="value",
        )

        mock_event_router.apply_typed.assert_called_once_with(
            mock_agent, "test_event", str, int, param="value"
        )
        assert res == "result"

    @patch("good_agent.agent.events.EventRouter")
    def test_apply_typed_sync(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.apply_typed_sync.return_value = "result"
        res = events_facade.apply_typed_sync(
            "test_event",
            params_type=str,
            return_type=int,
            param="value",
        )

        mock_event_router.apply_typed_sync.assert_called_once_with(
            mock_agent, "test_event", str, int, param="value"
        )
        assert res == "result"

    @patch("good_agent.agent.events.EventRouter")
    def test_typed(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.typed.return_value = "typed_wrapper"
        res = events_facade.typed(params_type=str, return_type=int)

        mock_event_router.typed.assert_called_once_with(mock_agent, str, int)
        assert res == "typed_wrapper"

    @patch("good_agent.agent.events.EventRouter")
    def test_broadcast_to(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.broadcast_to.return_value = 1
        other_router = MagicMock(spec=EventRouter)
        res = events_facade.broadcast_to(other_router)

        mock_event_router.broadcast_to.assert_called_once_with(
            mock_agent, other_router
        )
        assert res == 1

    @patch("good_agent.agent.events.EventRouter")
    def test_consume_from(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        other_router = MagicMock(spec=EventRouter)
        events_facade.consume_from(other_router)

        mock_event_router.consume_from.assert_called_once_with(
            mock_agent, other_router
        )

    @patch("good_agent.agent.events.EventRouter")
    def test_set_event_trace(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        events_facade.set_event_trace(True, verbosity=2, use_rich=False)

        mock_event_router.set_event_trace.assert_called_once_with(
            mock_agent, True, 2, False
        )

    @patch("good_agent.agent.events.EventRouter")
    def test_event_trace_enabled(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        # Mock the descriptor's __get__ method
        # Use a real class or spec to avoid MagicMock attribute issues with __get__
        mock_descriptor = MagicMock()
        # We need to attach the __get__ method in a way that MagicMock accepts
        type(mock_descriptor).__get__ = MagicMock(return_value=True)

        mock_event_router.event_trace_enabled = mock_descriptor
        res = events_facade.event_trace_enabled

        # Because we patched the class method, we check calls there
        mock_descriptor.__get__.assert_called_once_with(
            mock_agent, type(mock_agent)
        )
        assert res is True

    @patch("good_agent.agent.events.EventRouter")
    def test_ctx(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_descriptor = MagicMock()
        type(mock_descriptor).__get__ = MagicMock(return_value="context")

        mock_event_router.ctx = mock_descriptor
        res = events_facade.ctx

        mock_descriptor.__get__.assert_called_once_with(
            mock_agent, type(mock_agent)
        )
        assert res == "context"

    @patch("good_agent.agent.events.EventRouter")
    def test_join(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        events_facade.join(timeout=10.0)

        mock_event_router.join.assert_called_once_with(
            mock_agent, timeout=10.0
        )

    @patch("good_agent.agent.events.EventRouter")
    @pytest.mark.asyncio
    async def test_join_async(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.join_async = AsyncMock()

        await events_facade.join_async(timeout=10.0)

        mock_event_router.join_async.assert_called_once_with(
            mock_agent, timeout=10.0
        )

    @patch("good_agent.agent.events.EventRouter")
    def test_close(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        events_facade.close()

        mock_event_router.close.assert_called_once_with(mock_agent)

    @patch("good_agent.agent.events.EventRouter")
    @pytest.mark.asyncio
    async def test_async_close(
        self,
        mock_event_router: MagicMock,
        events_facade: AgentEventsFacade,
        mock_agent: Agent,
    ) -> None:
        mock_event_router.async_close = AsyncMock()

        await events_facade.async_close()

        mock_event_router.async_close.assert_called_once_with(mock_agent)
