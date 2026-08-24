"""
Distributed locking utilities using Redis.
Provides SETNX-style locking for safe concurrent execution of scheduled jobs.
"""
import asyncio
from typing import Optional, AsyncContextManager
from contextlib import asynccontextmanager
from shared.task_queue import get_queue_instance


class DistributedLock:
    """
    Redis-based distributed lock using SETNX pattern.
    
    Usage:
        async with DistributedLock("lock_name", ttl=60) as lock_acquired:
            if lock_acquired:
                # Execute critical section
                pass
            else:
                # Lock already held, skip execution
                pass
    """
    
    def __init__(self, lock_key: str, ttl: int = 60):
        """
        Initialize distributed lock.
        
        Args:
            lock_key: Unique identifier for the lock
            ttl: Time-to-live for the lock in seconds (should be longer than expected job duration)
        """
        self.lock_key = f"lock:{lock_key}"
        self.ttl = ttl
        self.acquired = False
        self._queue = None
    
    async def __aenter__(self) -> bool:
        """Acquire the lock using SETNX pattern."""
        try:
            self._queue = get_queue_instance()
            
            # Try to acquire lock using SETNX (set if not exists)
            # Redis SET command with NX and EX options
            if hasattr(self._queue, 'redis_client'):
                # Redis queue implementation
                result = await self._queue.redis_client.set(
                    self.lock_key,
                    "locked",
                    nx=True,  # Only set if key doesn't exist
                    ex=self.ttl  # Expire after TTL seconds
                )
                self.acquired = result is not None
            else:
                # Fallback for non-Redis queues (no distributed locking)
                # In this case, we simulate acquiring the lock but warn
                print(f"Warning: Distributed lock not available for {self.lock_key}, falling back to no-op")
                self.acquired = True  # Allow execution but warn
            
            return self.acquired
            
        except Exception as e:
            print(f"Error acquiring distributed lock {self.lock_key}: {e}")
            # On error, allow execution but log the issue
            self.acquired = True
            return self.acquired
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release the lock if it was acquired."""
        if self.acquired and self._queue and hasattr(self._queue, 'redis_client'):
            try:
                await self._queue.redis_client.delete(self.lock_key)
            except Exception as e:
                print(f"Error releasing distributed lock {self.lock_key}: {e}")
        
        self.acquired = False
        return False


@asynccontextmanager
async def with_distributed_lock(lock_key: str, ttl: int = 60) -> AsyncContextManager[bool]:
    """
    Context manager for distributed locking.
    
    Args:
        lock_key: Unique identifier for the lock
        ttl: Time-to-live for the lock in seconds
        
    Yields:
        bool: True if lock was acquired, False otherwise
        
    Example:
        async with with_distributed_lock("grace_period_sweep", ttl=120) as acquired:
            if acquired:
                # Execute job
                pass
            else:
                # Skip execution, lock already held
                pass
    """
    lock = DistributedLock(lock_key, ttl)
    try:
        acquired = await lock.__aenter__()
        yield acquired
    finally:
        await lock.__aexit__(None, None, None)