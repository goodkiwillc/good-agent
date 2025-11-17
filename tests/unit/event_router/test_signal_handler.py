from types import SimpleNamespace

from good_agent.core.signal_handler import SignalHandler


def test_signal_handler_registers_and_restores_handlers(monkeypatch):
    handler = SignalHandler()
    registered: dict[int, object] = {}

    def fake_signal(sig, func):
        registered[sig] = func
        return f"orig-{sig}"

    monkeypatch.setattr("signal.signal", fake_signal)

    router = SimpleNamespace()
    handler.register_router(router)
    assert registered
    handler.unregister_router(router)
    assert not handler._original_handlers


def test_cancel_all_tasks_cancels_router_tasks(monkeypatch):
    handler = SignalHandler()

    class DummyTask:
        def __init__(self):
            self.cancelled = False

        def done(self):
            return False

        def cancel(self):
            self.cancelled = True

    tasks = [DummyTask() for _ in range(2)]
    managed_tasks = {DummyTask(): None}
    router = SimpleNamespace(
        _tasks=tasks,
        _managed_tasks=managed_tasks,
        _event_loop=SimpleNamespace(is_running=lambda: False),
    )

    monkeypatch.setattr("signal.signal", lambda sig, func: None)
    handler.register_router(router)
    handler._cancel_all_tasks()
    assert all(task.cancelled for task in tasks)
    handler.unregister_router(router)
