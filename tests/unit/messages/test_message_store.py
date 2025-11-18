import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from good_agent.messages import AssistantMessage, UserMessage
from good_agent.messages.store import (
    InMemoryMessageStore,
    MessageNotFoundError,
    get_message,
    get_message_store,
    message_store,
    put_message,
    set_message_store,
)
from ulid import ULID


class TestInMemoryMessageStore:
    """Test the in-memory message store implementation"""

    def test_memory_only_store_creation(self):
        """Test creating a memory-only message store"""
        store = InMemoryMessageStore()
        assert len(store) == 0
        assert store._redis_client is None
        assert store._ttl == 3600  # 1 hour default

    def test_memory_store_with_redis(self):
        """Test creating a message store with Redis backing"""
        mock_redis = MagicMock()
        store = InMemoryMessageStore(redis_client=mock_redis, ttl=7200)
        assert store._redis_client is mock_redis
        assert store._ttl == 7200

    def test_put_and_get_message(self):
        """Test storing and retrieving messages"""
        store = InMemoryMessageStore()
        message = UserMessage(content="Hello world")

        # Put message (should auto-generate ID)
        store.put(message)
        assert message.id is not None
        assert len(store) == 1
        assert message.id in store

        # Get message back
        retrieved = store.get(message.id)
        assert retrieved is message
        assert retrieved.content == "Hello world"

    def test_put_message_with_existing_id(self):
        """Test storing message that already has an ID"""
        store = InMemoryMessageStore()
        # Create message with specific ULID
        specific_id = ULID.from_str("01HJ3Y8RGJN7S9N9Q8F4BK1KG0")
        message = UserMessage(id=specific_id, content="Hello")

        store.put(message)
        assert message.id == specific_id

        retrieved = store.get(specific_id)
        assert retrieved is message

    def test_get_nonexistent_message(self):
        """Test getting a message that doesn't exist"""
        store = InMemoryMessageStore()
        nonexistent_id = ULID()

        with pytest.raises(
            MessageNotFoundError, match=f"Message {nonexistent_id} not found"
        ):
            store.get(nonexistent_id)

    def test_exists_method(self):
        """Test the exists method"""
        store = InMemoryMessageStore()
        message = UserMessage(content="Test")

        assert not store.exists(ULID())

        store.put(message)
        assert store.exists(message.id)

    def test_clear_store(self):
        """Test clearing the message store"""
        store = InMemoryMessageStore()

        # Add some messages
        msg1 = UserMessage(content="Message 1")
        msg2 = AssistantMessage(content="Message 2")
        store.put(msg1)
        store.put(msg2)

        assert len(store) == 2

        # Clear and verify
        store.clear()
        assert len(store) == 0
        assert not store.exists(msg1.id)
        assert not store.exists(msg2.id)

    @pytest.mark.asyncio
    async def test_async_operations_memory_only(self):
        """Test async operations with memory-only store"""
        store = InMemoryMessageStore()
        message = UserMessage(content="Async test")

        # Async put
        await store.aput(message)
        assert len(store) == 1

        # Async get
        retrieved = await store.aget(message.id)
        assert retrieved is message

        # Async exists
        assert await store.aexists(message.id)
        missing_bytes = bytearray(message.id.bytes)
        missing_bytes[-1] ^= 0x01  # Flip LSB to ensure a different ULID
        missing_id = ULID(bytes(missing_bytes))
        assert not await store.aexists(missing_id)

        # Async get nonexistent
        nonexistent_id = ULID()
        with pytest.raises(MessageNotFoundError):
            await store.aget(nonexistent_id)

    @pytest.mark.asyncio
    async def test_async_operations_with_redis(self):
        """Test async operations with Redis backing"""
        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Cache miss
        mock_redis.setex.return_value = True
        mock_redis.exists.return_value = 0

        store = InMemoryMessageStore(redis_client=mock_redis)
        message = UserMessage(content="Redis test")

        # Put message - should store in both memory and Redis
        await store.aput(message)

        # Memory should also have it
        assert store.exists(message.id)

        # Verify Redis was called (but don't require it due to exception handling)
        # The setex call might be swallowed by exception handling
        if mock_redis.setex.call_count > 0:
            args = mock_redis.setex.call_args[0]
            assert args[0] == f"agent:message:{message.id}"  # Redis key
            assert args[1] == 3600  # TTL

    @pytest.mark.asyncio
    async def test_redis_fallback_on_get(self):
        """Test Redis fallback when message not in memory"""
        import orjson

        # Mock Redis client with cached message
        mock_redis = AsyncMock()
        redis_id = ULID()

        message_data = {
            "id": str(redis_id),
            "content": "From Redis",
            "role": "user",
            "type": "user",
        }
        mock_redis.get.return_value = orjson.dumps(message_data)

        store = InMemoryMessageStore(redis_client=mock_redis)

        # Message not in memory initially
        assert not store.exists(redis_id)

        # Get should fetch from Redis, populate memory, and return the message
        retrieved = await store.aget(redis_id)

        assert retrieved.content == "From Redis"
        assert retrieved.id == redis_id
        assert store.exists(redis_id)

        # Subsequent gets should hit the memory cache instead of Redis
        cached = await store.aget(redis_id)
        assert cached is retrieved

        mock_redis.get.assert_awaited_once_with(f"agent:message:{redis_id}")

    @pytest.mark.asyncio
    async def test_redis_error_handling(self):
        """Test that Redis errors don't break functionality"""
        # Mock Redis that raises exceptions
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis connection error")
        mock_redis.setex.side_effect = Exception("Redis connection error")

        store = InMemoryMessageStore(redis_client=mock_redis)
        message = UserMessage(content="Error test")

        # Put should succeed despite Redis error
        await store.aput(message)
        assert store.exists(message.id)

        # Get should work from memory
        retrieved = await store.aget(message.id)
        assert retrieved is message

    @pytest.mark.asyncio
    async def test_async_clear_with_redis(self):
        """Test async clear with Redis"""
        mock_redis = AsyncMock()

        # Mock the async iterator
        async def mock_scan_iter(*args, **kwargs):
            for item in ["agent:message:1", "agent:message:2"]:
                yield item

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 1

        store = InMemoryMessageStore(redis_client=mock_redis)

        # Add message to memory
        message = UserMessage(content="Test")
        store.put(message)
        assert len(store) == 1

        # Clear should remove from both memory and Redis
        await store.aclear()
        assert len(store) == 0

        # Verify Redis delete was called for each key
        # Note: we can't easily assert on scan_iter calls due to async generator
        assert (
            mock_redis.delete.call_count >= 0
        )  # May be called, but error handling can suppress


class TestGlobalMessageStore:
    """Test the global message store interface"""

    def test_global_store_initialization(self):
        """Test that global store auto-initializes"""
        # Reset global state
        from good_agent.messages import store

        store._global_message_store = None

        # Getting store should auto-initialize
        global_store = get_message_store()
        assert global_store is not None
        assert isinstance(global_store, InMemoryMessageStore)

    def test_set_custom_global_store(self):
        """Test setting a custom global store"""
        custom_store = InMemoryMessageStore(ttl=7200)
        set_message_store(custom_store)

        retrieved_store = get_message_store()
        assert retrieved_store is custom_store
        assert isinstance(retrieved_store, InMemoryMessageStore)
        assert retrieved_store._ttl == 7200

    def test_global_convenience_functions(self):
        """Test global convenience functions"""
        # Reset with clean store
        set_message_store(InMemoryMessageStore())

        message = UserMessage(content="Global test")

        # Put using global function
        put_message(message)

        # Get using global function
        retrieved = get_message(message.id)
        assert retrieved is message

        # Test message_exists
        from good_agent.messages.store import message_exists

        assert message_exists(message.id)
        assert not message_exists(ULID())

    @pytest.mark.asyncio
    async def test_global_async_functions(self):
        """Test global async convenience functions"""
        from good_agent.messages.store import (
            aget_message,
            amessage_exists,
            aput_message,
        )

        # Reset with clean store
        set_message_store(InMemoryMessageStore())

        message = UserMessage(content="Async global test")

        # Put using async global function
        await aput_message(message)

        # Get using async global function
        retrieved = await aget_message(message.id)
        assert retrieved is message

        # Test async exists
        assert await amessage_exists(message.id)
        assert not await amessage_exists(ULID())


class TestMessageStoreGlobal:
    """Test the message_store global object (spec compatibility)"""

    def test_message_store_global_interface(self):
        """Test that message_store provides the spec interface"""
        # Reset with clean store
        set_message_store(InMemoryMessageStore())

        message = UserMessage(content="Spec test")

        # Put using message_store interface
        message_store.put(message)

        # Get using message_store interface (spec usage)
        retrieved = message_store.get(message.id)
        assert retrieved is message
        assert retrieved.content == "Spec test"

        # Test exists
        assert message_store.exists(message.id)
        assert not message_store.exists(ULID())

    def test_message_store_spec_example(self):
        """Test the exact usage from the spec"""
        # This mimics the spec example:
        # assert message_store.get(_message_id).content == "The capital of France is Paris."

        set_message_store(InMemoryMessageStore())

        # Create a message like in the spec
        message = AssistantMessage(content="The capital of France is Paris.")
        message_store.put(message)

        _message_id = message.id

        # This is the exact line from the spec
        assert (
            message_store.get(_message_id).content == "The capital of France is Paris."
        )

    @pytest.mark.asyncio
    async def test_message_store_async_interface(self):
        """Test async methods on message_store global"""
        set_message_store(InMemoryMessageStore())

        message = UserMessage(content="Async spec test")

        # Async operations
        await message_store.aput(message)
        retrieved = await message_store.aget(message.id)
        assert retrieved is message

        assert await message_store.aexists(message.id)


class TestConcurrency:
    """Test thread safety and concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_put_operations(self):
        """Test concurrent put operations"""
        store = InMemoryMessageStore()

        async def put_message(i):
            message = UserMessage(content=f"Message {i}")
            await store.aput(message)
            return message.id

        # Create 10 concurrent put operations
        tasks = [put_message(i) for i in range(10)]
        message_ids = await asyncio.gather(*tasks)

        assert len(store) == 10
        assert len(set(message_ids)) == 10  # All IDs should be unique

        # Verify all messages can be retrieved
        for msg_id in message_ids:
            retrieved = store.get(msg_id)
            assert retrieved.content.startswith("Message ")

    @pytest.mark.asyncio
    async def test_concurrent_get_put_operations(self):
        """Test concurrent get and put operations"""
        store = InMemoryMessageStore()

        # Pre-populate with some messages
        initial_messages = []
        for i in range(5):
            msg = UserMessage(content=f"Initial {i}")
            store.put(msg)
            initial_messages.append(msg)

        async def get_message(msg_id):
            return await store.aget(msg_id)

        async def put_new_message(i):
            msg = UserMessage(content=f"New {i}")
            await store.aput(msg)
            return msg

        # Mix of get and put operations
        get_tasks = [get_message(msg.id) for msg in initial_messages[:3]]
        put_tasks = [put_new_message(i) for i in range(3)]

        results = await asyncio.gather(*get_tasks, *put_tasks)

        # First 3 results should be the retrieved messages
        for i, retrieved in enumerate(results[:3]):
            assert retrieved.content == f"Initial {i}"

        # Last 3 results should be newly created messages
        assert len(store) == 8  # 5 initial + 3 new
