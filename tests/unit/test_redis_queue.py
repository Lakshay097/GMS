"""Unit tests for Redis Queue implementation."""
import os
import pytest
from datetime import datetime, timezone

# Force memory queue for these tests unless Redis is explicitly configured
os.environ["QUEUE_PROVIDER"] = "memory"

from shared.task_queue import RedisQueue, InMemoryQueue, get_queue_instance, reset_queue_instance


@pytest.mark.asyncio
async def test_redis_queue_enqueue_dequeue():
    """Test basic enqueue and dequeue operations using memory queue as proxy."""
    queue = InMemoryQueue()  # Using memory queue for testing
    queue_name = "test_queue"
    job_data = {"test": "data", "value": 123}
    
    # Enqueue a job
    message_id = await queue.enqueue(queue_name, job_data)
    assert message_id is not None
    
    # Dequeue the job
    messages = await queue.dequeue(queue_name, max_messages=10)
    assert len(messages) == 1
    assert messages[0]["Body"] == job_data
    assert messages[0]["ReceiptHandle"] == message_id


@pytest.mark.asyncio
async def test_redis_queue_delayed_job():
    """Test delayed job enqueue and dequeue using memory queue as proxy."""
    queue = InMemoryQueue()  # Using memory queue for testing
    queue_name = "test_delayed_queue"
    job_data = {"delayed": "job"}
    
    # Enqueue with delay
    message_id = await queue.enqueue(queue_name, job_data, delay_seconds=5)
    assert message_id is not None
    
    # Note: Memory queue doesn't implement true delayed jobs
    # This test verifies the interface works, but actual delay logic is provider-specific
    # For Redis queue, delayed jobs use sorted sets with timestamps
    messages = await queue.dequeue(queue_name, max_messages=10)
    # Memory queue will return the job immediately (no true delay implementation)
    # This is expected behavior for the memory queue implementation


@pytest.mark.asyncio
async def test_redis_queue_multiple_messages():
    """Test enqueue and dequeue of multiple messages using memory queue as proxy."""
    queue = InMemoryQueue()  # Using memory queue for testing
    queue_name = "test_multi_queue"
    
    # Enqueue multiple jobs
    message_ids = []
    for i in range(5):
        job_data = {"index": i}
        message_id = await queue.enqueue(queue_name, job_data)
        message_ids.append(message_id)
    
    # Dequeue all jobs
    messages = await queue.dequeue(queue_name, max_messages=10)
    assert len(messages) == 5
    
    # Verify all message IDs are present
    receipt_handles = [msg["ReceiptHandle"] for msg in messages]
    for message_id in message_ids:
        assert message_id in receipt_handles


@pytest.mark.asyncio
async def test_redis_queue_create_queue():
    """Test queue creation using memory queue as proxy."""
    queue = InMemoryQueue()  # Using memory queue for testing
    queue_name = "test_create_queue"
    
    # Create queue
    result = await queue.create_queue(queue_name)
    assert result is True


@pytest.mark.asyncio
async def test_redis_queue_delete_message():
    """Test message deletion using memory queue as proxy."""
    queue = InMemoryQueue()  # Using memory queue for testing
    queue_name = "test_delete_queue"
    job_data = {"delete": "me"}
    
    # Enqueue a job
    message_id = await queue.enqueue(queue_name, job_data)
    
    # Dequeue the job
    messages = await queue.dequeue(queue_name, max_messages=10)
    assert len(messages) == 1
    
    # Delete the message
    receipt_handle = messages[0]["ReceiptHandle"]
    result = await queue.delete_message(queue_name, receipt_handle)
    assert result is True


@pytest.mark.asyncio
async def test_redis_queue_factory():
    """Test queue factory function."""
    # Test memory queue
    os.environ["QUEUE_PROVIDER"] = "memory"
    reset_queue_instance()
    queue = get_queue_instance()
    assert isinstance(queue, InMemoryQueue)
    
    # Test Redis queue (will fail if redis not installed or connection string invalid, which is expected)
    try:
        os.environ["QUEUE_PROVIDER"] = "redis"
        os.environ["QUEUE_CONNECTION_STRING"] = "redis://localhost:6379"
        reset_queue_instance()
        queue = get_queue_instance()
        assert isinstance(queue, RedisQueue)
    except (ImportError, ValueError):
        # Redis not installed or invalid connection string, skip this part
        pass
    finally:
        # Reset to memory for other tests
        os.environ["QUEUE_PROVIDER"] = "memory"
        reset_queue_instance()


@pytest.mark.skipif(
    os.getenv("REDIS_TEST_URL") is None,
    reason="Redis test URL not configured"
)
@pytest.mark.asyncio
async def test_redis_queue_integration():
    """Integration test with real Redis instance."""
    redis_url = os.getenv("REDIS_TEST_URL")
    os.environ["QUEUE_PROVIDER"] = "redis"
    os.environ["QUEUE_CONNECTION_STRING"] = redis_url
    reset_queue_instance()
    
    try:
        queue = get_queue_instance()
        queue_name = "test_integration_queue"
        job_data = {"integration": "test"}
        
        # Enqueue
        message_id = await queue.enqueue(queue_name, job_data)
        assert message_id is not None
        
        # Dequeue
        messages = await queue.dequeue(queue_name, max_messages=10)
        assert len(messages) == 1
        assert messages[0]["Body"] == job_data
        
        # Cleanup
        await queue.delete_message(queue_name, messages[0]["ReceiptHandle"])
        
    finally:
        # Reset to memory for other tests
        os.environ["QUEUE_PROVIDER"] = "memory"
        reset_queue_instance()


@pytest.mark.asyncio
async def test_redis_queue_structure():
    """Test that RedisQueue has correct structure and methods."""
    try:
        # Try to instantiate RedisQueue to check structure
        os.environ["QUEUE_CONNECTION_STRING"] = "redis://localhost:6379"
        queue = RedisQueue()
        
        # Check that all required methods exist
        assert hasattr(queue, 'enqueue')
        assert hasattr(queue, 'dequeue')
        assert hasattr(queue, 'delete_message')
        assert hasattr(queue, 'create_queue')
        
        # Check that methods are async
        import inspect
        assert inspect.iscoroutinefunction(queue.enqueue)
        assert inspect.iscoroutinefunction(queue.dequeue)
        assert inspect.iscoroutinefunction(queue.delete_message)
        assert inspect.iscoroutinefunction(queue.create_queue)
        
    except (ImportError, ValueError):
        # Redis not installed or invalid connection string, skip structure check
        pytest.skip("redis package not installed or not configured")
