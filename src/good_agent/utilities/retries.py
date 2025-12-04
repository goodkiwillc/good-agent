from __future__ import annotations

import abc
import asyncio
import datetime
import functools
import inspect
import logging
import random
import sys
from collections import ChainMap
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, MutableMapping
from enum import Enum, auto
from typing import (
    Any,
    Generic,
    ParamSpec,
    TypeVar,
    cast,
)

logger = logging.getLogger(__name__)

TIME_UNIT_TYPE = int | float | datetime.timedelta

P = ParamSpec("P")
T = TypeVar("T")

MaybeAsyncCallable = Callable[P, Awaitable[T]] | Callable[P, T]

MAX_WAIT = sys.maxsize / 2


def _to_seconds(time_unit: TIME_UNIT_TYPE) -> float:
    """
    Convert time unit to seconds for internal calculations.

    ARGS:
        time_unit: Time duration in various formats (int/float seconds, timedelta)

    RETURNS:
        float: Time duration in seconds

    NOTES:
        - Handles int/float seconds directly
        - Converts timedelta objects to total seconds
        - Used internally by backoff strategies
    """
    return float(
        time_unit.total_seconds() if isinstance(time_unit, datetime.timedelta) else time_unit
    )


class wait_base(abc.ABC):
    """Abstract base class for wait strategies."""

    @abc.abstractmethod
    def __call__(self, retry_state: RetryState[Any]) -> float:
        pass

    def __add__(self, other: wait_base) -> wait_combine:
        return wait_combine(self, other)

    def __radd__(self, other: object) -> wait_combine | wait_base:
        # make it possible to use multiple waits with the built-in sum function
        if other == 0:  # type: ignore[comparison-overlap]
            return self
        if isinstance(other, wait_base):
            return self.__add__(other)
        raise TypeError("Unsupported operand type for wait_base addition")


WaitBaseT = wait_base | Callable[["RetryState[Any]"], float | int]


class wait_fixed(wait_base):
    """Wait strategy that waits a fixed amount of time between each retry."""

    def __init__(self, wait: TIME_UNIT_TYPE) -> None:
        self.wait_fixed = _to_seconds(wait)

    def __call__(self, retry_state: RetryState[Any]) -> float:
        return self.wait_fixed


class wait_none(wait_fixed):
    """Wait strategy that doesn't wait at all before retrying."""

    def __init__(self) -> None:
        super().__init__(0)


class wait_random(wait_base):
    """Wait strategy that waits a random amount of time between min/max."""

    def __init__(self, min: TIME_UNIT_TYPE = 0, max: TIME_UNIT_TYPE = 1) -> None:  # noqa
        self.wait_random_min = _to_seconds(min)
        self.wait_random_max = _to_seconds(max)

    def __call__(self, retry_state: RetryState[Any]) -> float:
        return self.wait_random_min + (
            random.random() * (self.wait_random_max - self.wait_random_min)
        )


class wait_combine(wait_base):
    """Combine several waiting strategies."""

    def __init__(self, *strategies: wait_base) -> None:
        self.wait_funcs = strategies

    def __call__(self, retry_state: RetryState[Any]) -> float:
        return sum(x(retry_state=retry_state) for x in self.wait_funcs)


class wait_chain(wait_base):
    """Chain two or more waiting strategies.

    If all strategies are exhausted, the very last strategy is used
    thereafter.

    For example::

        @retry(wait=wait_chain(*[wait_fixed(1) for i in range(3)] +
                               [wait_fixed(2) for j in range(5)] +
                               [wait_fixed(5) for k in range(4)))
        def wait_chained():
            print("Wait 1s for 3 attempts, 2s for 5 attempts and 5s
                   thereafter.")
    """

    def __init__(self, *strategies: wait_base) -> None:
        self.strategies = strategies

    def __call__(self, retry_state: RetryState[Any]) -> float:
        wait_func_no = min(max(retry_state.attempt, 1), len(self.strategies))
        wait_func = self.strategies[wait_func_no - 1]
        return wait_func(retry_state=retry_state)


class wait_incrementing(wait_base):
    """Wait an incremental amount of time after each attempt.

    Starting at a starting value and incrementing by a value for each attempt
    (and restricting the upper limit to some maximum value).
    """

    def __init__(
        self,
        start: TIME_UNIT_TYPE = 0,
        increment: TIME_UNIT_TYPE = 100,
        max: TIME_UNIT_TYPE = MAX_WAIT,  # noqa
    ) -> None:
        self.start = _to_seconds(start)
        self.increment = _to_seconds(increment)
        self.max = _to_seconds(max)

    def __call__(self, retry_state: RetryState[Any]) -> float:
        result = self.start + (self.increment * (retry_state.attempt - 1))
        return max(0, min(result, self.max))


class wait_exponential(wait_base):
    """Wait strategy that applies exponential backoff.

    It allows for a customized multiplier and an ability to restrict the
    upper and lower limits to some maximum and minimum value.

    The intervals are fixed (i.e. there is no jitter), so this strategy is
    suitable for balancing retries against latency when a required resource is
    unavailable for an unknown duration, but *not* suitable for resolving
    contention between multiple processes for a shared resource. Use
    wait_random_exponential for the latter case.
    """

    def __init__(
        self,
        multiplier: int | float = 1,
        max: TIME_UNIT_TYPE = MAX_WAIT,  # noqa
        exp_base: int | float = 2,
        min: TIME_UNIT_TYPE = 0,  # noqa
    ) -> None:
        self.multiplier = multiplier
        self.min = _to_seconds(min)
        self.max = _to_seconds(max)
        self.exp_base = exp_base

    def __call__(self, retry_state: RetryState[Any]) -> float:
        try:
            exp = self.exp_base ** (retry_state.attempt - 1)
            result = self.multiplier * exp
        except OverflowError:
            return self.max
        return max(max(0, self.min), min(result, self.max))


class wait_random_exponential(wait_exponential):
    """Random wait with exponentially widening window.

    An exponential backoff strategy used to mediate contention between multiple
    uncoordinated processes for a shared resource in distributed systems. This
    is the sense in which "exponential backoff" is meant in e.g. Ethernet
    networking, and corresponds to the "Full Jitter" algorithm described in
    this blog post:

    https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/

    Each retry occurs at a random time in a geometrically expanding interval.
    It allows for a custom multiplier and an ability to restrict the upper
    limit of the random interval to some maximum value.

    Example::

        wait_random_exponential(
            multiplier=0.5,  # initial window 0.5s
            max=60,
        )  # max 60s timeout

    When waiting for an unavailable resource to become available again, as
    opposed to trying to resolve contention for a shared resource, the
    wait_exponential strategy (which uses a fixed interval) may be preferable.

    """

    def __call__(self, retry_state: RetryState[Any]) -> float:
        high = super().__call__(retry_state=retry_state)
        return random.uniform(self.min, high)


class wait_exponential_jitter(wait_base):
    """Wait strategy that applies exponential backoff and jitter.

    It allows for a customized initial wait, maximum wait and jitter.

    This implements the strategy described here:
    https://cloud.google.com/storage/docs/retry-strategy

    The wait time is min(initial * 2**n + random.uniform(0, jitter), maximum)
    where n is the retry count.
    """

    def __init__(
        self,
        initial: float = 1,
        max: float = MAX_WAIT,  # noqa
        exp_base: float = 2,
        jitter: float = 1,
    ) -> None:
        self.initial = initial
        self.max = max
        self.exp_base = exp_base
        self.jitter = jitter

    def __call__(self, retry_state: RetryState[Any]) -> float:
        jitter = random.uniform(0, self.jitter)
        try:
            exp = self.exp_base ** (retry_state.attempt - 1)
            result = self.initial * exp + jitter
        except OverflowError:
            result = self.max
        return max(0, min(result, self.max))


class RetryAction(Enum):
    """Possible actions after an attempt."""

    RETRY = auto()  # Retry the operation
    STOP = auto()  # Stop retrying, with failure
    SUCCEED = auto()  # Stop retrying, with success


class RetryState(Generic[T]):
    """Object representing the current state of a retry operation."""

    __match_args__ = (
        "attempt",
        "success",
        "first_attempt",
        "final_attempt",
        "exception",
        "result",
        "kwargs",
    )

    def __init__(
        self,
        parent: Retry[T],
        attempt: int,
        function: MaybeAsyncCallable,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        exception: Exception | None = None,
        result: T | None = None,
    ):
        self._parent: Retry[T] = parent
        self._args: tuple[Any, ...] = args
        self._kwargs: ChainMap[str, Any] = ChainMap(dict(kwargs))

        self.attempt = attempt
        self.function: MaybeAsyncCallable = function

        self.exception = exception
        self.result = result

        self.action: RetryAction = RetryAction.RETRY

    @property
    def kwargs(self) -> ChainMap[str, Any]:
        return self._kwargs

    @kwargs.setter
    def kwargs(self, value: Mapping[str, Any] | None) -> None:
        if value is None:
            self._kwargs = self._kwargs.new_child()
        else:
            self._kwargs = self._kwargs.new_child(dict(value))

    @property
    def args(self) -> tuple[Any, ...]:
        return self._args

    @args.setter
    def args(self, value: tuple[Any, ...]) -> None:
        if value:
            self._args = value

    @property
    def max_attempts(self) -> int:
        return self._parent.max_attempts

    @property
    def success(self) -> bool:
        """Whether the current attempt was successful."""
        return self.exception is None and self.result is not None

    @property
    def first_attempt(self) -> bool:
        """Whether this is the first attempt."""
        return self.attempt == 1

    @property
    def final_attempt(self) -> bool:
        """Whether this was the last allowed attempt."""
        return self.attempt == self.max_attempts

    def retry(self, *args: Any, **kwargs: Any) -> None:
        """
        Force a retry with optionally modified arguments.

        Args:
            **kwargs: New keyword arguments to update for the next attempt
        """
        self._parent.log("RetryState.retry()")
        self.action = RetryAction.RETRY
        self.args = args
        self.kwargs = kwargs

    def stop(self) -> None:
        """Stop the retry loop with failure."""
        self._parent.log("RetryState.stop()")
        self.action = RetryAction.STOP

    def succeed_with(self, result: T) -> None:
        """
        Force the retry loop to succeed with a custom result.

        Args:
            result: The result to return
        """
        self.action = RetryAction.SUCCEED
        self._parent.log(f"Forcing success with {result=}")
        self.result = result


class Retry(Generic[T]):
    """
    A context manager for managing retries with customizable behavior.

    Usage:
        with Retry(max_attempts=3) as retry:
            async for state in retry(my_function, arg1, kwarg1=value1):
                match state:
                    case RetryState(success=True, result=result):
                        # Handle success
                    case RetryState(exception=exc):
                        # Handle failure
    """

    def __init__(
        self,
        max_attempts: int = 3,
        wait: WaitBaseT | None = None,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        break_and_suppress: tuple[type[BaseException], ...] = (),
        break_and_propagate: tuple[type[BaseException], ...] = (
            KeyboardInterrupt,
            asyncio.CancelledError,
        ),
        debug: bool = False,
        timeout: float | None = None,
    ):
        """
        Initialize the retry manager.

        Args:
            max_attempts: Maximum number of attempts (default: 3)
            wait: Function to calculate wait time between attempts (None for no wait)
            retry_on: Exception types that should trigger retries
            break_on: Exception types that should always fail
            logger: Logger for retry events
            timeout: Timeout for each attempt in seconds (None for no timeout)
        """
        self.max_attempts = max(1, max_attempts)
        self.wait: Callable[[RetryState[Any]], float] = self._resolve_wait(wait)
        self._retry_on = retry_on
        self._break_and_suppress = break_and_suppress
        self._break_and_propagate = break_and_propagate
        # self.logger = logger or logging.getLogger(__name__)
        self._debug = debug
        self.timeout = timeout

    @staticmethod
    def _resolve_wait(wait: WaitBaseT | None) -> Callable[[RetryState[Any]], float]:
        if wait is None:
            return lambda _: 0.0
        if isinstance(wait, wait_base):
            return lambda state: float(wait(state))
        return lambda state: float(wait(state))

    def log(
        self,
        message: str,
        options: Mapping[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Log a message with the retry logger."""
        _ = options or {}
        if self._debug:
            logger.debug(message, *args, **kwargs)

    def __enter__(self) -> Retry[T]:
        """Enter the context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the context manager."""
        pass

    def __call__(
        self,
        function: MaybeAsyncCallable,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[RetryState[T]]:
        """
        Create a retry operation for the function with the given arguments.

        Args:
            function: The function to retry
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            An async generator yielding RetryState objects
        """
        return self._retry_generator(function, args, dict(kwargs))

    async def _retry_generator(
        self,
        function: MaybeAsyncCallable,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> AsyncGenerator[RetryState[T]]:
        """Async generator for retry operations."""
        is_async = inspect.iscoroutinefunction(function)
        current_attempt = 0
        current_args = args
        current_kwargs: MutableMapping[str, Any] = dict(kwargs)

        while current_attempt < self.max_attempts:
            self.log(f"iteration {current_attempt=}")
            current_attempt += 1

            # Create the current state
            state = RetryState(
                parent=self,
                attempt=current_attempt,
                function=function,
                args=current_args,
                kwargs=current_kwargs,
            )

            # Apply backoff if not first attempt
            if current_attempt > 1:
                wait_time = self.wait(state)
                self.log(f"Wait time for attempt {current_attempt}: {wait_time:.2f}s")
                if wait_time > 0:
                    self.log(f"Waiting {wait_time:.2f}s before attempt {current_attempt}")
                    await asyncio.sleep(wait_time)

            # Execute the function
            try:
                if self.timeout is not None:
                    # logger.debug(f"Executing with timeout: {self.timeout:.2f}s")
                    result = await self._execute_with_timeout(
                        function, state.args, state.kwargs, is_async
                    )
                else:
                    result = await self._execute(function, state.args, state.kwargs, is_async)
                # logger.debug(f"{result=}")
                state.result = result
                state.action = RetryAction.SUCCEED
            except Exception as exc:
                state.exception = exc
                self.log(f"Attempt {current_attempt} failed with: {type(exc).__name__}: {exc}")

                if isinstance(exc, self._break_and_propagate):
                    state.action = RetryAction.STOP
                    raise exc

                if isinstance(exc, self._break_and_suppress):
                    state.action = RetryAction.STOP

                # Check if we should stop retrying based on exception type
                elif not isinstance(exc, self._retry_on):
                    self.log(
                        f"Exception {type(exc).__name__} is not in retry_exceptions, stopping retry loop"
                    )
                    state.action = RetryAction.STOP

            # Yield state to caller and let them process it
            yield state

            self.log(f"{state.attempt=} {state.kwargs=} {state.result=} {state.action=} ")

            # Check what action to take based on state
            if state.action == RetryAction.SUCCEED:
                # Forced success with custom result
                self.log(f"Forced success after attempt {current_attempt}")
                # state.result = state._custom_result
                state.exception = None
                break

            elif state.action == RetryAction.STOP:
                # Forced stop
                self.log(f"Forced stop after attempt {current_attempt}")
                break

            else:  # RetryAction.RETRY
                # Update for next attempt
                current_args = state.args
                current_kwargs = dict(state.kwargs)

                # Check if we've reached max attempts
                if current_attempt >= self.max_attempts:
                    self.log(f"Max attempts ({self.max_attempts}) reached, stopping retry loop")
                    break

    async def _execute_with_timeout(
        self,
        function: MaybeAsyncCallable,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        is_async: bool,
    ) -> T:
        """Execute the function with a timeout."""
        return await asyncio.wait_for(
            self._execute(function, args, kwargs, is_async), timeout=self.timeout
        )

    async def _execute(
        self,
        function: MaybeAsyncCallable,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        is_async: bool,
    ) -> T:
        """Execute the function with the given arguments."""
        if is_async:
            async_callable = cast(Callable[..., Awaitable[T]], function)
            return await async_callable(*args, **kwargs)
        else:
            # Run synchronous functions in a thread pool
            loop = asyncio.get_running_loop()
            sync_callable = cast(Callable[..., T], function)
            return await loop.run_in_executor(
                None, functools.partial(sync_callable, *args, **kwargs)
            )
