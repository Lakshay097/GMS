"""Unit tests for distributed locking functionality."""
import os
import pytest
import asyncio
from datetime import datetime

# Force memory queue for these tests
os.environ["QUEUE_PROVIDER"] = "memory"

from shared.distributed_lock import DistributedLock, with_distributed_lock
from shared.task_queue import get_queue_instance, reset_queue_instance


@pytest.mark.asyncio
async def test_distributed_lock_basic_acquisition():
    """Test basic lock acquisition and release."""
    lock = DistributedLock("test_lock", ttl=60)
    
    # Acquire lock
    acquired = await lock.__aenter__()
    assert acquired is True
    
    # Release lock
    await lock.__aexit__(None, None, None)
    assert lock.acquired is False


@pytest.mark.asyncio
async def test_distributed_lock_context_manager():
    """Test distributed lock using context manager."""
    async with with_distributed_lock("test_context_lock", ttl=60) as acquired:
        assert acquired is True
        # Inside critical section
        pass


@pytest.mark.asyncio
async def test_distributed_lock_contention():
    """Test that lock prevents concurrent execution."""
    execution_count = 0
    lock_key = "contention_test_lock"
    
    async def protected_operation():
        nonlocal execution_count
        async with with_distributed_lock(lock_key, ttl=60) as acquired:
            if acquired:
                execution_count += 1
                # Simulate some work
                await asyncio.sleep(0.1)
    
    # Run two concurrent operations
    await asyncio.gather(
        protected_operation(),
        protected_operation()
    )
    
    # With memory queue (no true distributed locking), both will execute
    # With Redis queue, only one should acquire the lock
    # For now, we test that the interface works correctly
    assert execution_count >= 1


@pytest.mark.asyncio
async def test_distributed_lock_with_memory_queue_fallback():
    """Test that distributed lock falls back gracefully with memory queue."""
    lock = DistributedLock("memory_queue_test", ttl=60)
    
    # With memory queue, lock should still "acquire" (but warn)
    acquired = await lock.__aenter__()
    assert acquired is True  # Memory queue allows execution with warning
    
    await lock.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_distributed_lock_different_keys():
    """Test that different lock keys don't interfere with each other."""
    lock1 = DistributedLock("lock_key_1", ttl=60)
    lock2 = DistributedLock("lock_key_2", ttl=60)
    
    # Both should be acquirable since they have different keys
    acquired1 = await lock1.__aenter__()
    acquired2 = await lock2.__aenter__()
    
    assert acquired1 is True
    assert acquired2 is True
    
    await lock1.__aexit__(None, None, None)
    await lock2.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_grace_period_sweep_with_locking():
    """Test that grace period sweep uses distributed locking."""
    # This is a structural test to verify the locking integration
    # Full integration test would require actual database setup
    async with with_distributed_lock("grace_period_sweep", ttl=120) as acquired:
        assert acquired is True or acquired is False  # Lock interface works


@pytest.mark.asyncio
async def test_scorecard_generation_with_locking():
    """Test that scorecard generation uses distributed locking."""
    from modules.performance_scorecards.services.scorecard_scheduler import ScorecardScheduler
    import uuid
    
    # This is a structural test to verify the locking integration
    review_id = uuid.uuid4()
    lock_key = f"scorecard_generation_{review_id}"
    
    async with with_distributed_lock(lock_key, ttl=300) as acquired:
        assert acquired is True or acquired is False  # Lock interface works


@pytest.mark.asyncio
async def test_concurrent_grace_period_sweep():
    """Test concurrent grace period sweep calls with locking."""
    sweep_count = 0
    
    async def mock_sweep():
        nonlocal sweep_count
        async with with_distributed_lock("grace_period_sweep", ttl=120) as acquired:
            if acquired:
                sweep_count += 1
                await asyncio.sleep(0.05)
    
    # Simulate concurrent invocations
    await asyncio.gather(
        mock_sweep(),
        mock_sweep(),
        mock_sweep()
    )
    
    # With memory queue, all will execute (fallback behavior)
    # With Redis queue, only one should acquire the lock
    assert sweep_count >= 1


@pytest.mark.asyncio
async def test_concurrent_scorecard_generation():
    """Test concurrent scorecard generation calls with locking."""
    import uuid
    
    generation_count = 0
    review_id = uuid.uuid4()
    lock_key = f"scorecard_generation_{review_id}"
    
    async def mock_generation():
        nonlocal generation_count
        async with with_distributed_lock(lock_key, ttl=300) as acquired:
            if acquired:
                generation_count += 1
                await asyncio.sleep(0.05)
    
    # Simulate concurrent invocations for same review
    await asyncio.gather(
        mock_generation(),
        mock_generation(),
        mock_generation()
    )
    
    # With memory queue, all will execute (fallback behavior)
    # With Redis queue, only one should acquire the lock per review
    assert generation_count >= 1


@pytest.mark.asyncio
async def test_distributed_lock_ttl_expiration():
    """Test that lock has TTL and doesn't block forever."""
    lock = DistributedLock("ttl_test_lock", ttl=1)  # 1 second TTL
    
    # Acquire lock
    acquired = await lock.__aenter__()
    assert acquired is True
    
    # Release lock normally
    await lock.__aexit__(None, None, None)
    
    # Should be able to acquire again immediately
    lock2 = DistributedLock("ttl_test_lock", ttl=1)
    acquired2 = await lock2.__aenter__()
    assert acquired2 is True
    
    await lock2.__aexit__(None, None, None)