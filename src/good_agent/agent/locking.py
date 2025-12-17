from __future__ import annotations

import asyncio
import threading
import time


class ReentrantAsyncLock:
    """A re-entrant lock that works across event loops and threads."""

    def __init__(self) -> None:
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._lock_thread: threading.Thread | None = None
        self._owner_id: int | None = None
        self._depth = 0

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _ensure_lock_loop(self) -> asyncio.AbstractEventLoop:
        loop = self._lock_loop
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=loop.run_forever, name="ReentrantAsyncLock", daemon=True)
            thread.start()
            while not loop.is_running():
                time.sleep(0.001)
            self._lock_loop = loop
            self._lock_thread = thread
        return loop

    @property
    def locked(self) -> bool:
        lock = self._lock
        return lock.locked() if lock else False

    async def _acquire_on_lock_loop(self, owner_id: int | None) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()

        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("ReentrantAsyncLock requires an active asyncio Task")

        owner = owner_id or id(current)

        if self._owner_id == owner:
            self._depth += 1
            return

        await self._lock.acquire()
        self._owner_id = owner
        self._depth = 1

    async def acquire(self, owner_id: int | None = None) -> None:
        loop = self._ensure_lock_loop()
        await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(
                self._acquire_on_lock_loop(owner_id), loop
            )
        )

    async def _release_on_lock_loop(self, owner_id: int | None) -> None:
        if self._lock is None:
            raise RuntimeError("Cannot release an uninitialized lock")

        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("ReentrantAsyncLock can only be released by its owner")

        owner = owner_id or id(current)

        if self._owner_id != owner:
            raise RuntimeError("ReentrantAsyncLock can only be released by its owner")

        if self._depth <= 0:
            raise RuntimeError("ReentrantAsyncLock release called too many times")

        self._depth -= 1
        if self._depth == 0:
            self._owner_id = None
            self._lock.release()

    async def release(self, owner_id: int | None = None) -> None:
        loop = self._lock_loop
        if loop is None:
            raise RuntimeError("ReentrantAsyncLock has not been acquired")

        await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(
                self._release_on_lock_loop(owner_id), loop
            )
        )

    async def __aenter__(self) -> ReentrantAsyncLock:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.release()

    def close(self) -> None:
        loop = self._lock_loop
        thread = self._lock_thread
        self._lock_loop = None
        self._lock_thread = None

        if loop is None:
            return

        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
            if thread and thread.is_alive():
                thread.join(timeout=1)

        if not loop.is_closed():
            loop.close()
