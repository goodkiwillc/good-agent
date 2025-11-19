from __future__ import annotations

import threading

from good_agent.core.event_router import EventContext, EventRouter


def test_concurrent_handler_registration_is_safe() -> None:
    router = EventRouter()
    threads: list[threading.Thread] = []
    per_thread = 50
    thread_count = 8

    def register(index: int) -> None:
        for i in range(per_thread):

            def handler(_: EventContext, marker=(index, i)) -> None:
                return None

            router.on("thread:test", priority=100 + index)(handler)

    for idx in range(thread_count):
        thread = threading.Thread(target=register, args=(idx,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    count = router._handler_registry.get_handler_count("thread:test")
    assert count == thread_count * per_thread


def test_concurrent_emit_calls_do_not_deadlock() -> None:
    router = EventRouter()
    hits: list[int] = []
    lock = threading.Lock()

    @router.on("thread:emit")
    def handler(_: EventContext) -> None:
        with lock:
            hits.append(1)

    def emit_many() -> None:
        for _ in range(200):
            router.do("thread:emit")

    threads = [threading.Thread(target=emit_many) for _ in range(4)]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    router.join_sync()
    assert len(hits) == 800


def test_emit_and_register_concurrently() -> None:
    router = EventRouter()
    recorded: list[int] = []
    lock = threading.Lock()

    @router.on("thread:mixed")
    def baseline(ctx: EventContext) -> None:
        with lock:
            recorded.append(ctx.parameters["value"])  # type: ignore[index]

    def emitter() -> None:
        for i in range(100):
            router.do("thread:mixed", value=i)

    def registrar() -> None:
        for offset in range(10):

            def handler(ctx: EventContext, marker=offset) -> None:
                with lock:
                    recorded.append(ctx.parameters["value"])  # type: ignore[index]

            router.on("thread:mixed", priority=offset)(handler)

    t1 = threading.Thread(target=emitter)
    t2 = threading.Thread(target=registrar)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    router.join_sync()

    assert len(recorded) == 100
