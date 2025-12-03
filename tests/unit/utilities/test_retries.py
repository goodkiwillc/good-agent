"""Tests for utilities/retries.py module."""

from typing import Any

import pytest
from good_agent.utilities.retries import (
    Retry,
    RetryAction,
    RetryState,
    wait_exponential,
    wait_fixed,
    wait_none,
    wait_random,
)


class TestWaitStrategies:
    """Tests for wait strategies."""

    def test_wait_none(self):
        """Test wait_none strategy returns zero wait time."""
        wait = wait_none()
        state: RetryState[Any] = RetryState(
            parent=Retry(),
            attempt=1,
            function=lambda: None,
            args=(),
            kwargs={},
        )
        assert wait(state) == 0

    def test_wait_fixed(self):
        """Test wait_fixed strategy returns fixed wait time."""
        wait = wait_fixed(2)
        state: RetryState[Any] = RetryState(
            parent=Retry(),
            attempt=1,
            function=lambda: None,
            args=(),
            kwargs={},
        )
        assert wait(state) == 2

    def test_wait_random_range(self):
        """Test wait_random strategy returns value in range."""
        wait = wait_random(min=1, max=3)
        state: RetryState[Any] = RetryState(
            parent=Retry(),
            attempt=1,
            function=lambda: None,
            args=(),
            kwargs={},
        )

        # Test multiple times to ensure randomness
        for _ in range(10):
            wait_time = wait(state)
            assert 1 <= wait_time <= 3

    def test_wait_exponential_increases(self):
        """Test wait_exponential strategy increases with attempts."""
        wait = wait_exponential(multiplier=1, exp_base=2)

        # Create states for different attempts
        state1: RetryState[Any] = RetryState(
            parent=Retry(),
            attempt=1,
            function=lambda: None,
            args=(),
            kwargs={},
        )
        state2: RetryState[Any] = RetryState(
            parent=Retry(),
            attempt=2,
            function=lambda: None,
            args=(),
            kwargs={},
        )
        state3: RetryState[Any] = RetryState(
            parent=Retry(),
            attempt=3,
            function=lambda: None,
            args=(),
            kwargs={},
        )

        wait1 = wait(state1)  # 1 * 2^0 = 1
        wait2 = wait(state2)  # 1 * 2^1 = 2
        wait3 = wait(state3)  # 1 * 2^2 = 4

        assert wait1 < wait2 < wait3


class TestRetryState:
    """Tests for RetryState class."""

    def test_retry_state_initialization(self):
        """Test RetryState initializes correctly."""
        parent: Retry[Any] = Retry()
        state: RetryState[Any] = RetryState(
            parent=parent,
            attempt=1,
            function=lambda: None,
            args=(1, 2),
            kwargs={"key": "value"},
        )

        assert state.attempt == 1
        assert state.args == (1, 2)
        assert state.kwargs["key"] == "value"
        assert state.action == RetryAction.RETRY

    def test_retry_state_success_property(self):
        """Test success property."""
        parent: Retry[Any] = Retry()

        # Successful state
        state_success: RetryState[Any] = RetryState(
            parent=parent,
            attempt=1,
            function=lambda: None,
            args=(),
            kwargs={},
            result="success",
        )
        assert state_success.success is True

        # Failed state
        state_failed: RetryState[Any] = RetryState(
            parent=parent,
            attempt=1,
            function=lambda: None,
            args=(),
            kwargs={},
            exception=ValueError("error"),
        )
        assert state_failed.success is False

    def test_retry_state_first_attempt(self):
        """Test first_attempt property."""
        parent: Retry[Any] = Retry()

        state1: RetryState[Any] = RetryState(
            parent=parent, attempt=1, function=lambda: None, args=(), kwargs={}
        )
        state2: RetryState[Any] = RetryState(
            parent=parent, attempt=2, function=lambda: None, args=(), kwargs={}
        )

        assert state1.first_attempt is True
        assert state2.first_attempt is False

    def test_retry_state_final_attempt(self):
        """Test final_attempt property."""
        parent: Retry[Any] = Retry(max_attempts=3)

        state2: RetryState[Any] = RetryState(
            parent=parent, attempt=2, function=lambda: None, args=(), kwargs={}
        )
        state3: RetryState[Any] = RetryState(
            parent=parent, attempt=3, function=lambda: None, args=(), kwargs={}
        )

        assert state2.final_attempt is False
        assert state3.final_attempt is True


class TestRetryBasic:
    """Tests for basic Retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_successful_function(self):
        """Test retry with immediately successful function."""

        async def successful_func():
            return "success"

        retry: Retry[Any] = Retry(max_attempts=3)
        async for state in retry(successful_func):
            assert state.result == "success"
            assert state.exception is None
            assert state.success is True

    @pytest.mark.asyncio
    async def test_retry_failing_function(self):
        """Test retry with always failing function."""
        attempt_count = 0

        async def failing_func():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Failed")

        retry: Retry[Any] = Retry(max_attempts=3)
        final_state = None

        async for state in retry(failing_func):
            final_state = state

        assert attempt_count == 3
        assert final_state is not None
        assert final_state.exception is not None
        assert isinstance(final_state.exception, ValueError)

    @pytest.mark.asyncio
    async def test_retry_eventually_succeeds(self):
        """Test retry that succeeds after failures."""
        attempt_count = 0

        async def eventually_successful():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Not yet")
            return "success"

        retry: Retry[Any] = Retry(max_attempts=5)
        final_state = None

        async for state in retry(eventually_successful):
            final_state = state
            if state.success:
                break

        assert final_state is not None
        assert final_state.result == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_respects_max_attempts(self):
        """Test that retry respects max_attempts setting."""
        attempt_count = 0

        async def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Always fails")

        retry: Retry[Any] = Retry(max_attempts=5)

        async for state in retry(always_fails):
            pass

        assert attempt_count == 5

    @pytest.mark.asyncio
    async def test_retry_with_sync_function(self):
        """Test retry works with synchronous functions."""

        def sync_func():
            return "sync result"

        retry: Retry[Any] = Retry(max_attempts=3)
        async for state in retry(sync_func):
            assert state.result == "sync result"
            assert state.success is True
