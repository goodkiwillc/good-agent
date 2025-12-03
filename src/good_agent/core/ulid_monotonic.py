from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from ulid import ULID


@dataclass
class MonotonicState:
    """Internal state for monotonic ULID generation."""

    last_timestamp: int = 0
    last_randomness: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


class MonotonicULID:
    """
    Thread-safe monotonic ULID generator that ensures unique IDs even when
    multiple ULIDs are generated within the same millisecond.

    This class maintains internal state to track the last generated timestamp
    and randomness value. When multiple ULIDs are requested within the same
    millisecond, it increments the randomness component to maintain uniqueness
    and sort order.

    Example:
        >>> generator = MonotonicULID()
        >>> ulid1 = generator.generate()
        >>> ulid2 = generator.generate()
        >>> assert ulid1 < ulid2  # Always true, even if generated in same ms
    """

    _state: ClassVar[MonotonicState] = MonotonicState()
    _async_lock: ClassVar[asyncio.Lock | None] = None

    @classmethod
    def _get_async_lock(cls) -> asyncio.Lock:
        """Get or create the async lock for the current event loop."""
        if cls._async_lock is None:
            cls._async_lock = asyncio.Lock()
        return cls._async_lock

    @classmethod
    def generate(cls) -> ULID:
        """
        Generate a new monotonic ULID.

        Returns:
            ULID: A new ULID instance that is guaranteed to be greater than
                  any previously generated ULID from this generator.

        Raises:
            ValueError: If the randomness component would overflow (extremely rare).

        Example:
            >>> generator = MonotonicULID()
            >>> ulid = generator.generate()
            >>> print(ulid)
        """
        with cls._state.lock:
            # Get current timestamp in milliseconds
            current_timestamp = int(datetime.now(UTC).timestamp() * 1000)

            # Check if we're in the same millisecond as the last generation
            if current_timestamp == cls._state.last_timestamp:
                # Increment the randomness to maintain monotonicity
                new_randomness = cls._state.last_randomness + 1

                # Check for overflow (80 bits for randomness)
                if new_randomness >= (1 << 80):
                    raise ValueError(
                        "Randomness component overflow. Too many ULIDs generated "
                        "in the same millisecond."
                    )

                cls._state.last_randomness = new_randomness
            else:
                # New millisecond, generate fresh randomness
                # Use ULID's internal random generation
                temp_ulid = ULID()
                # Extract randomness from the generated ULID
                ulid_bytes = temp_ulid.bytes
                randomness_bytes = ulid_bytes[6:]
                cls._state.last_randomness = int.from_bytes(randomness_bytes, "big")
                cls._state.last_timestamp = current_timestamp

            # Construct the ULID from timestamp and randomness
            # ULID format: 48 bits timestamp + 80 bits randomness
            timestamp_bytes = current_timestamp.to_bytes(6, "big")
            randomness_bytes = cls._state.last_randomness.to_bytes(10, "big")
            ulid_bytes = timestamp_bytes + randomness_bytes

            return ULID(ulid_bytes)

    @classmethod
    async def generate_async(cls) -> ULID:
        """
        Async version of generate() for use in async contexts.

        Returns:
            ULID: A new monotonic ULID instance.

        Example:
            >>> generator = MonotonicULID()
            >>> ulid = await generator.generate_async()
        """
        async_lock = cls._get_async_lock()
        async with async_lock:
            # Use the sync lock within async to maintain consistency
            return cls.generate()

    @classmethod
    def reset(cls) -> None:
        """
        Reset the internal state of the generator.

        This method should only be used in testing scenarios where you need
        to reset the generator state between tests.
        """
        with cls._state.lock:
            cls._state.last_timestamp = 0
            cls._state.last_randomness = 0


class MonotonicULIDField(ULID):
    """
    A Pydantic-compatible ULID field that uses monotonic generation.

    This class extends the standard ULID class to provide automatic monotonic
    generation when used as a Pydantic field with default_factory.

    Example:
        >>> from pydantic import BaseModel, Field
        >>>
        >>> class MyModel(BaseModel):
        ...     id: MonotonicULIDField = Field(
        ...         default_factory=MonotonicULIDField.create
        ...     )
        >>> model1 = MyModel()
        >>> model2 = MyModel()
        >>> assert model1.id < model2.id
    """

    @classmethod
    def create(cls) -> MonotonicULIDField:
        """
        Create a new monotonic ULID instance.

        This method is designed to be used as a default_factory in Pydantic models.

        Returns:
            MonotonicULIDField: A new monotonic ULID instance.
        """
        ulid = MonotonicULID.generate()
        # Cast to the correct type since cls() returns Self which is compatible
        return cls(ulid.bytes)  # type: ignore[return-value]

    @classmethod
    async def create_async(cls) -> MonotonicULIDField:
        """
        Async version of create() for use in async contexts.

        Returns:
            MonotonicULIDField: A new monotonic ULID instance.
        """
        ulid = await MonotonicULID.generate_async()
        return cls(ulid.bytes)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """
        Get the Pydantic core schema for this field.

        This ensures proper validation and serialization in Pydantic models.
        """

        def validate_ulid(value: Any) -> MonotonicULIDField:
            if isinstance(value, cls):
                return value  # type: ignore[return-value]
            elif isinstance(value, ULID):
                return cls(value.bytes)  # type: ignore[return-value]
            elif isinstance(value, str):
                return cls.from_str(value)  # type: ignore[return-value]
            elif isinstance(value, bytes):
                return cls(value)  # type: ignore[return-value]
            elif isinstance(value, int):
                return cls(value.to_bytes(16, "big"))  # type: ignore[return-value]
            else:
                raise ValueError(f"Cannot convert {type(value).__name__} to MonotonicULIDField")

        return core_schema.no_info_plain_validator_function(
            validate_ulid,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x),
                when_used="json",
            ),
        )

    def __str__(self) -> str:
        """Return the string representation of the ULID."""
        return super().__str__()

    def __repr__(self) -> str:
        """Return the repr of the ULID."""
        return f"MonotonicULIDField('{str(self)}')"


def create_monotonic_ulid() -> ULID:
    """
    Convenience function to generate a monotonic ULID.

    This is a simple wrapper around MonotonicULID.generate() for easier imports.

    Returns:
        ULID: A new monotonic ULID instance.

    Example:
        >>> from good_agent.core.ulid_monotonic import create_monotonic_ulid
        >>> ulid = create_monotonic_ulid()
    """
    return MonotonicULID.generate()


async def create_monotonic_ulid_async() -> ULID:
    """
    Async convenience function to generate a monotonic ULID.

    Returns:
        ULID: A new monotonic ULID instance.

    Example:
        >>> from good_agent.core.ulid_monotonic import (
        ...     create_monotonic_ulid_async,
        ... )
        >>> ulid = await create_monotonic_ulid_async()
    """
    return await MonotonicULID.generate_async()


__all__ = [
    "MonotonicULID",
    "MonotonicULIDField",
    "create_monotonic_ulid",
    "create_monotonic_ulid_async",
]
