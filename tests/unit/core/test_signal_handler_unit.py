import builtins
import signal
from types import SimpleNamespace
from unittest.mock import MagicMock

import good_agent.core.signal_handler as sh
import pytest
from good_agent.core.signal_handler import SignalHandler, _RouterRef


class DummyTask:
    def __init__(self, done: bool = False):
        self._done = done
        self.cancelled = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancelled = True


class LoopStub:
    def __init__(self):
        self.stopped = False

    def is_running(self) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True

    def call_soon_threadsafe(self, callback, *args):
        callback(*args)


def test_router_ref_handles_non_weakref_objects():
    sentinel = []

    ref = _RouterRef(42, lambda r: sentinel.append(r))
    assert ref() == 42
    assert hash(ref) == hash(ref)
    assert ref == ref


def test_signal_handler_installs_and_restores_handlers(monkeypatch):
    handler = SignalHandler()
    calls: list[tuple[int, object]] = []

    def fake_signal(sig: int, func):
        calls.append((sig, func))
        return f"orig-{sig}"

    monkeypatch.setattr(sh.signal, "signal", fake_signal)
    monkeypatch.setattr(sh.sys, "platform", "linux")

    handler._install_handlers()

    assert calls[0][0] == signal.SIGINT
    assert calls[0][1] == handler._handle_signal
    assert signal.SIGINT in handler._original_handlers

    calls.clear()
    handler._restore_handlers()
    # Should restore both SIGINT and SIGTERM
    restored_sigs = {sig for sig, _ in calls}
    assert signal.SIGINT in restored_sigs
    if hasattr(signal, "SIGTERM"):
        assert signal.SIGTERM in restored_sigs
    assert handler._original_handlers == {}


def test_handle_signal_triggers_shutdown(monkeypatch):
    handler = SignalHandler()
    cancel = MagicMock()
    event_set = MagicMock()
    monkeypatch.setattr(handler, "_cancel_all_tasks", cancel)
    monkeypatch.setattr(handler._shutdown_event, "set", event_set)

    class RunnerHandler:
        def __init__(self):
            self.func = SimpleNamespace(__qualname__="Runner._on_sigint")

        def __call__(self, *args, **kwargs):
            raise AssertionError("Runner handler should not be invoked")

    handler._original_handlers[signal.SIGINT] = RunnerHandler()

    original_keyboard_interrupt = builtins.KeyboardInterrupt
    sentinel_interrupt = type("SentinelInterrupt", (Exception,), {})
    monkeypatch.setitem(builtins.__dict__, "KeyboardInterrupt", sentinel_interrupt)

    with pytest.raises(sentinel_interrupt):
        handler._handle_signal(signal.SIGINT, None)

    cancel.assert_called_once()
    event_set.assert_called_once()
    assert handler.is_shutdown_initiated() is True

    # Restore original KeyboardInterrupt for subsequent assertions
    monkeypatch.setitem(builtins.__dict__, "KeyboardInterrupt", original_keyboard_interrupt)

    exit_mock = MagicMock()
    exit_mock.side_effect = SystemExit(1)
    monkeypatch.setattr(sh.sys, "exit", exit_mock)
    with pytest.raises(SystemExit):
        handler._handle_signal(signal.SIGINT, None)
    exit_mock.assert_called_once_with(1)


def test_cancel_all_tasks_cancels_router_work(monkeypatch):
    handler = SignalHandler()

    loop = LoopStub()
    task_a = DummyTask()
    task_b = DummyTask(done=True)
    managed_task = DummyTask()
    extra_task = DummyTask()

    class RouterA:
        pass

    router_a = RouterA()
    router_a._tasks = [task_a, task_b]
    router_a.tasks = SimpleNamespace(managed_tasks={managed_task: None})
    router_a._event_loop = loop

    class RouterB:
        pass

    router_b = RouterB()
    router_b._tasks = [extra_task]
    router_b._managed_tasks = {extra_task: None}

    handler._registered_routers = {
        _RouterRef(router_a, handler._on_router_deleted),
        _RouterRef(router_b, handler._on_router_deleted),
    }

    handler._cancel_all_tasks()

    assert task_a.cancelled is True
    assert managed_task.cancelled is True
    assert extra_task.cancelled is True
    assert loop.stopped is True
