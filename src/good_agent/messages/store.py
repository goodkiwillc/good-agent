import asyncio
import weakref
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from ulid import ULID

if TYPE_CHECKING:
    from good_agent.messages import Message

from good_agent.messages.utilities import MessageFactory


class MessageNotFoundError(Exception):
    """Raised when a message cannot be found in the store"""

    pass


@runtime_checkable
class MessageStore(Protocol):
    """Protocol for message storage implementations"""

    def get(self, message_id: ULID) -> Message:
        """Get a message by ID (synchronous)"""
        ...

    async def aget(self, message_id: ULID) -> Message:
        """Get a message by ID (asynchronous)"""
        ...

    def put(self, message: Message) -> None:
        """Store a message (synchronous)"""
        ...

    async def aput(self, message: Message) -> None:
        """Store a message (asynchronous)"""
        ...

    def exists(self, message_id: ULID) -> bool:
        """Check if a message exists"""
        ...

    async def aexists(self, message_id: ULID) -> bool:
        """Check if a message exists (async)"""
        ...


class InMemoryMessageStore:
    """
    In-memory message store with optional Redis backing.

    Provides fast access to messages with optional persistence layer.
    Task-safe operations using asyncio locks.
    """

    def __init__(self, redis_client: Any = None, ttl: int = 3600):
        """
        Initialize the message store.

        Args:
            redis_client: Optional Redis client for backing store
            ttl: Time-to-live for Redis entries in seconds (default: 1 hour)
        """
        self._memory_cache: dict[str, Message] = {}
        self._redis_client = redis_client
        self._ttl = ttl
        self._lock = asyncio.Lock()

        # Weak reference set to track all message stores for cleanup
        self._weak_refs: set[weakref.ref] = set()

    def get(self, message_id: ULID) -> Message:
        """
        Get a message by ID (synchronous).

        First checks memory cache, falls back to Redis if available.

        Args:
            message_id: The unique message identifier

        Returns:
            The message object

        Raises:
            MessageNotFoundError: If message is not found
        """
        # Check memory cache first
        message_id_str = str(message_id)
        if message_id_str in self._memory_cache:
            return self._memory_cache[message_id_str]

        # If we have Redis, try to fetch from there
        if self._redis_client:
            # For sync operation, we can't use async Redis
            # This is a limitation - sync get only works with memory
            raise MessageNotFoundError(
                f"Message {message_id} not found in memory cache. Use aget() for Redis fallback."
            )

        raise MessageNotFoundError(f"Message {message_id} not found")

    async def aget(self, message_id: ULID) -> Message:
        """
        Get a message by ID (asynchronous).

        First checks memory cache, then Redis if available.

        Args:
            message_id: The unique message identifier

        Returns:
            The message object

        Raises:
            MessageNotFoundError: If message is not found
        """
        async with self._lock:
            # Check memory cache first
            message_id_str = str(message_id)
            if message_id_str in self._memory_cache:
                return self._memory_cache[message_id_str]

            # Try Redis if available
            if self._redis_client:
                try:
                    try:
                        import orjson

                        json_loads = orjson.loads
                    except ImportError:
                        import json

                        json_loads = json.loads

                    redis_key = f"agent:message:{message_id_str}"
                    cached_data = await self._redis_client.get(redis_key)

                    if cached_data:
                        # Handle both bytes and string data
                        if isinstance(cached_data, bytes):
                            cached_data = cached_data.decode()

                        # Deserialize message from Redis
                        message_data = json_loads(cached_data)
                        # MessageFactory.from_dict now handles both old and new formats
                        message = MessageFactory.from_dict(message_data)

                        # Store in memory cache for faster future access
                        self._memory_cache[message_id_str] = message
                        return message

                except Exception:
                    # Log error but don't fail - Redis is optional
                    # In production, would use proper logging
                    pass

            raise MessageNotFoundError(f"Message {message_id} not found")

    def put(self, message: Message) -> None:
        """
        Store a message (synchronous).

        Stores in memory cache immediately.

        Args:
            message: The message to store
        """
        # Messages always have IDs due to default_factory
        self._memory_cache[str(message.id)] = message

    async def aput(self, message: Message) -> None:
        """
        Store a message (asynchronous).

        Stores in memory cache and Redis if available.

        Args:
            message: The message to store
        """
        # Messages always have IDs due to default_factory
        async with self._lock:
            # Store in memory cache
            self._memory_cache[str(message.id)] = message

            # Store in Redis if available
            if self._redis_client:
                try:
                    try:
                        import orjson

                        json_dumps = orjson.dumps
                    except ImportError:
                        import json

                        def json_dumps(x):  # type: ignore[misc]
                            return json.dumps(x).encode()

                    redis_key = f"agent:message:{message.id}"
                    # Use new serialization method if available
                    if hasattr(message, "serialize_for_storage"):
                        message_data = message.serialize_for_storage()
                    else:
                        # Fallback to standard model_dump
                        message_data = message.model_dump()
                    cached_data = json_dumps(message_data)

                    # Store with TTL
                    await self._redis_client.setex(redis_key, self._ttl, cached_data)

                except Exception:
                    # Log error but don't fail - Redis is optional
                    # In production, would use proper logging
                    pass

    def exists(self, message_id: ULID) -> bool:
        """
        Check if a message exists (synchronous).

        Only checks memory cache for sync operation.

        Args:
            message_id: The message identifier

        Returns:
            True if message exists in memory cache
        """
        return str(message_id) in self._memory_cache

    async def aexists(self, message_id: ULID) -> bool:
        """
        Check if a message exists (asynchronous).

        Checks both memory cache and Redis.

        Args:
            message_id: The message identifier

        Returns:
            True if message exists
        """
        async with self._lock:
            # Check memory first
            message_id_str = str(message_id)
            if message_id_str in self._memory_cache:
                return True

            # Check Redis if available
            if self._redis_client:
                try:
                    redis_key = f"agent:message:{message_id_str}"
                    exists_count = await self._redis_client.exists(redis_key)
                    return bool(exists_count > 0)
                except Exception:
                    # Redis error - fall back to memory-only
                    pass

            return False

    def clear(self) -> None:
        """Clear all messages from memory cache"""
        self._memory_cache.clear()

    async def aclear(self) -> None:
        """Clear all messages from memory cache and Redis"""
        async with self._lock:
            self._memory_cache.clear()

            if self._redis_client:
                try:
                    # Clear all agent message keys
                    pattern = "agent:message:*"
                    async for key in self._redis_client.scan_iter(match=pattern):
                        await self._redis_client.delete(key)
                except Exception:
                    # Redis error - continue anyway
                    pass

    def __len__(self) -> int:
        """Return number of messages in memory cache"""
        return len(self._memory_cache)

    def __contains__(self, message_id: ULID) -> bool:
        """Check if message exists in memory cache"""
        return str(message_id) in self._memory_cache


# Global message store instance
# Will be initialized by the agent framework
_global_message_store: MessageStore | None = None


def get_message_store() -> MessageStore:
    """
    Get the global message store instance.

    Returns:
        The global message store

    Raises:
        RuntimeError: If no message store has been configured
    """
    if _global_message_store is None:
        # Auto-initialize with in-memory store
        set_message_store(InMemoryMessageStore())

    assert _global_message_store is not None
    return _global_message_store


def set_message_store(store: MessageStore) -> None:
    """
    Set the global message store instance.

    Args:
        store: The message store to use globally
    """
    global _global_message_store
    _global_message_store = store


# Convenience functions that delegate to global store
def get_message(message_id: ULID) -> Message:
    """Get a message by ID using the global store"""
    return get_message_store().get(message_id)


async def aget_message(message_id: ULID) -> Message:
    """Get a message by ID using the global store (async)"""
    return await get_message_store().aget(message_id)


def put_message(message: Message) -> None:
    """Store a message using the global store"""
    get_message_store().put(message)


async def aput_message(message: Message) -> None:
    """Store a message using the global store (async)"""
    await get_message_store().aput(message)


def message_exists(message_id: ULID) -> bool:
    """Check if a message exists using the global store"""
    return get_message_store().exists(message_id)


async def amessage_exists(message_id: ULID) -> bool:
    """Check if a message exists using the global store (async)"""
    return await get_message_store().aexists(message_id)


# For the spec compatibility - the global store can be accessed as message_store
class MessageStoreGlobal:
    """Global message store interface matching the spec usage"""

    def get(self, message_id: ULID) -> Message:
        """Get a message by ID"""
        return get_message(message_id)

    async def aget(self, message_id: ULID) -> Message:
        """Get a message by ID (async)"""
        return await aget_message(message_id)

    def put(self, message: Message) -> None:
        """Store a message"""
        put_message(message)

    async def aput(self, message: Message) -> None:
        """Store a message (async)"""
        await aput_message(message)

    def exists(self, message_id: ULID) -> bool:
        """Check if message exists"""
        return message_exists(message_id)

    async def aexists(self, message_id: ULID) -> bool:
        """Check if message exists (async)"""
        return await amessage_exists(message_id)


# Global instance for spec compatibility: message_store.get(id)
message_store = MessageStoreGlobal()
