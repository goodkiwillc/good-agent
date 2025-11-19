import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from good_agent.agent.core import Agent
from good_agent.cli.run import run_agent


def _run_coroutine(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@patch("good_agent.cli.run.asyncio.run")
@patch("good_agent.cli.run.run_interactive_loop", new_callable=AsyncMock)
@patch("good_agent.cli.run.load_agent_from_path")
def test_run_agent_executes_interactive_loop(mock_load, mock_loop, mock_asyncio_run):
    agent = MagicMock(spec=Agent)
    mock_load.return_value = (agent, {})
    mock_asyncio_run.side_effect = _run_coroutine

    run_agent("module:agent")

    mock_load.assert_called_once_with("module:agent")
    mock_loop.assert_awaited_once_with(agent)
    mock_asyncio_run.assert_called_once()


@patch("good_agent.cli.run.asyncio.run")
@patch("good_agent.cli.run.run_interactive_loop", new_callable=AsyncMock)
@patch("good_agent.cli.run.load_agent_from_path")
def test_run_agent_factory_receives_extra_args(
    mock_load, mock_loop, mock_asyncio_run
):
    agent = MagicMock(spec=Agent)
    factory = MagicMock(return_value=agent)
    mock_load.return_value = (factory, {})
    mock_asyncio_run.side_effect = _run_coroutine

    run_agent("module:factory", extra_args=["--verbose", "true"])

    factory.assert_called_once_with("--verbose", "true")
    mock_loop.assert_awaited_once_with(agent)


@patch("builtins.print")
@patch("good_agent.cli.run.asyncio.run")
@patch("good_agent.cli.run.run_interactive_loop", new_callable=AsyncMock)
@patch("good_agent.cli.run.load_agent_from_path")
def test_run_agent_rejects_non_agent_objects(
    mock_load, mock_loop, mock_asyncio_run, mock_print
):
    factory = MagicMock(return_value="not-an-agent")
    mock_load.return_value = (factory, {})

    run_agent("module:factory")

    factory.assert_called_once_with()
    mock_print.assert_called_once_with(
        "Error: The object at 'module:factory' is not an Agent instance (got str)."
    )
    mock_loop.assert_not_called()
    mock_loop.assert_not_awaited()
    mock_asyncio_run.assert_not_called()


@patch("builtins.print")
@patch("good_agent.cli.run.asyncio.run")
@patch("good_agent.cli.run.run_interactive_loop", new_callable=AsyncMock)
@patch("good_agent.cli.run.load_agent_from_path")
def test_run_agent_reports_load_errors(
    mock_load, mock_loop, mock_asyncio_run, mock_print
):
    mock_load.side_effect = Exception("boom")

    run_agent("module:agent")

    mock_print.assert_called_once_with("Error loading agent: boom")
    mock_loop.assert_not_called()
    mock_asyncio_run.assert_not_called()


@patch("builtins.print")
@patch("good_agent.cli.run.asyncio.run")
@patch("good_agent.cli.run.run_interactive_loop", new_callable=AsyncMock)
@patch("good_agent.cli.run.load_agent_from_path")
def test_run_agent_reports_factory_errors(
    mock_load, mock_loop, mock_asyncio_run, mock_print
):
    factory = MagicMock(side_effect=ValueError("factory boom"))
    mock_load.return_value = (factory, {})

    run_agent("module:factory", extra_args=["--foo", "bar"])

    factory.assert_called_once_with("--foo", "bar")
    mock_print.assert_called_once_with("Error instantiating agent factory: factory boom")
    mock_loop.assert_not_called()
    mock_asyncio_run.assert_not_called()

