"""Regression tests ensuring legacy Agent helpers emit DeprecationWarning."""

from __future__ import annotations

import warnings

import pytest

from good_agent import Agent


def _assert_warns(callable_obj):
    """Helper to assert a DeprecationWarning is emitted."""

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        result = callable_obj()

    assert any(w.category is DeprecationWarning for w in caught), (
        "Expected DeprecationWarning"
    )
    return result


@pytest.mark.asyncio
async def test_context_lifecycle_shims_emit_warnings() -> None:
    async with Agent("context shim warnings") as agent:
        forked = _assert_warns(lambda: agent.fork(include_messages=False))
        assert forked is not None
        # Clean up forked agent to avoid leaked tasks
        await forked.events.async_close()

        ctx = _assert_warns(lambda: agent.thread_context())
        assert ctx is not None


@pytest.mark.asyncio
async def test_message_management_shims_emit_warnings() -> None:
    async with Agent("message shim warnings") as agent:
        agent.append("hello world")
        replacement = agent.model.create_message("replacement", role="user")
        _assert_warns(lambda: agent.replace_message(0, replacement))

        _assert_warns(lambda: agent.set_system_message("system prompt"))


@pytest.mark.asyncio
async def test_rendering_and_print_shims_emit_warnings() -> None:
    async with Agent("rendering shim warnings") as agent:
        agent.append("ready")

        _assert_warns(lambda: agent.print())
        _assert_warns(lambda: agent.get_rendering_context())

        async def _async_context():
            await agent.get_rendering_context_async()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            await _async_context()
        assert any(w.category is DeprecationWarning for w in caught)


@pytest.mark.asyncio
async def test_version_and_token_helpers_emit_warnings() -> None:
    async with Agent("version shim warnings") as agent:
        agent.append("count me")

        _assert_warns(lambda: agent.get_token_count())
        _assert_warns(lambda: agent.get_token_count_by_role())
        _assert_warns(lambda: agent.current_version)


__all__ = [
    "test_context_lifecycle_shims_emit_warnings",
    "test_message_management_shims_emit_warnings",
    "test_rendering_and_print_shims_emit_warnings",
    "test_version_and_token_helpers_emit_warnings",
]
