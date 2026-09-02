"""
Async job queue interface and implementation.
Provider is pinned in env-and-secrets.md §5 (QUEUE_PROVIDER).
Abstract interface allows swapping providers per AQ3 assumption.
"""
import os
from typing import Optional, Dict, Any, Callable
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from datetime import datetime, timezone
from shared.datetime_utils import utc_now

load_dotenv()

QUEUE_PROVIDER = os.getenv("QUEUE_PROVIDER", "memory")
QUEUE_CONNECTION_STRING = os.getenv("QUEUE_CONNECTION_STRING")


class JobQueue(ABC):
    """
    Abstract interface for job queue providers.
    Allows swapping between SQS, Kafka, etc. per AQ3.
    """
    
    @abstractmethod
    async def enqueue(
        self,
        queue_name: str,
        job_data: Dict[str, Any],
        delay_seconds: int = 0
    ) -> str:
        """
        Enqueue a job.
        
        Args:
            queue_name: Name of the queue
            job_data: Job payload data
            delay_seconds: Delay before job is available
            
        Returns:
            Job/message ID
        """
        pass
    
    @abstractmethod
    async def dequeue(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20
    ) -> list:
        """
        Dequeue jobs for processing.
        
        Args:
            queue_name: Name of the queue
            max_messages: Maximum number of messages to retrieve
            wait_time_seconds: Long polling wait time
            
        Returns:
            List of job messages
        """
        pass
    
    @abstractmethod
    async def delete_message(
        self,
        queue_name: str,
        receipt_handle: str
    ) -> bool:
        """
        Delete a processed message.
        
        Args:
            queue_name: Name of the queue
            receipt_handle: Message receipt handle
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def create_queue(
        self,
        queue_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a queue.
        
        Args:
            queue_name: Name of the queue
            attributes: Optional queue attributes
            
        Returns:
            True if successful, False otherwise
        """
        pass


class InMemoryQueue(JobQueue):
    """
    In-process queue for development and tests.
    R-40/ADR-05: dispatch still async relative to the triggering request.
    """

    def __init__(self):
        self._queues: Dict[str, list] = {}

    async def enqueue(
        self,
        queue_name: str,
        job_data: Dict[str, Any],
        delay_seconds: int = 0,
    ) -> str:
        import uuid

        message_id = str(uuid.uuid4())
        self._queues.setdefault(queue_name, []).append(
            {"id": message_id, "body": job_data, "delay_seconds": delay_seconds}
        )
        return message_id

    async def dequeue(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> list:
        queue = self._queues.get(queue_name, [])
        messages = queue[:max_messages]
        self._queues[queue_name] = queue[max_messages:]
        return [
            {"Body": msg["body"], "ReceiptHandle": msg["id"]}
            for msg in messages
        ]

    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        return True

    async def create_queue(
        self,
        queue_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        self._queues.setdefault(queue_name, [])
        return True


class SQSQueue(JobQueue):
    """
    AWS SQS implementation of JobQueue.
    Used when QUEUE_PROVIDER=sqs.
    """
    
    def __init__(self):
        self.connection_string = QUEUE_CONNECTION_STRING
        # Import boto3 only when needed
        try:
            import boto3
            self.client = boto3.client(
                'sqs',
                endpoint_url=self.connection_string if self.connection_string else None
            )
        except ImportError:
            raise ImportError("boto3 is required for SQS queue. Install with: pip install boto3")
    
    async def enqueue(
        self,
        queue_name: str,
        job_data: Dict[str, Any],
        delay_seconds: int = 0
    ) -> str:
        """Enqueue a job to SQS."""
        import json
        import asyncio
        
        def _enqueue():
            response = self.client.send_message(
                QueueUrl=queue_name,
                MessageBody=json.dumps(job_data),
                DelaySeconds=delay_seconds
            )
            return response['MessageId']
        
        return await asyncio.to_thread(_enqueue)
    
    async def dequeue(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20
    ) -> list:
        """Dequeue jobs from SQS."""
        import asyncio
        
        def _dequeue():
            response = self.client.receive_message(
                QueueUrl=queue_name,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=['All']
            )
            return response.get('Messages', [])
        
        return await asyncio.to_thread(_dequeue)
    
    async def delete_message(
        self,
        queue_name: str,
        receipt_handle: str
    ) -> bool:
        """Delete a processed message from SQS."""
        import asyncio
        
        def _delete():
            self.client.delete_message(
                QueueUrl=queue_name,
                ReceiptHandle=receipt_handle
            )
            return True
        
        try:
            return await asyncio.to_thread(_delete)
        except Exception:
            return False
    
    async def create_queue(
        self,
        queue_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create an SQS queue."""
        import asyncio
        
        def _create():
            try:
                self.client.create_queue(
                    QueueName=queue_name,
                    Attributes=attributes or {}
                )
                return True
            except self.client.exceptions.QueueNameExists:
                return True
            except Exception:
                return False
        
        return await asyncio.to_thread(_create)


class KafkaQueue(JobQueue):
    """
    Kafka implementation of JobQueue.
    Used when QUEUE_PROVIDER=kafka.
    Provides ordering guarantees for escalation timers per AQ3.
    """
    
    def __init__(self):
        self.connection_string = QUEUE_CONNECTION_STRING
        # Import kafka-python only when needed
        try:
            from kafka import KafkaProducer, KafkaConsumer
            self.producer = None
            self.consumer = None
        except ImportError:
            raise ImportError("kafka-python is required for Kafka queue. Install with: pip install kafka-python")
    
    async def enqueue(
        self,
        queue_name: str,
        job_data: Dict[str, Any],
        delay_seconds: int = 0
    ) -> str:
        """Enqueue a job to Kafka topic."""
        import json
        import asyncio
        
        def _enqueue():
            if not self.producer:
                from kafka import KafkaProducer
                self.producer = KafkaProducer(
                    bootstrap_servers=self.connection_string,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
            future = self.producer.send(queue_name, value=job_data)
            return future.get(timeout=10)
        
        return await asyncio.to_thread(_enqueue)
    
    async def dequeue(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20
    ) -> list:
        """Dequeue jobs from Kafka topic."""
        import asyncio
        
        def _dequeue():
            if not self.consumer:
                from kafka import KafkaConsumer
                self.consumer = KafkaConsumer(
                    queue_name,
                    bootstrap_servers=self.connection_string,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest'
                )
            
            messages = []
            for _ in range(max_messages):
                try:
                    message = next(self.consumer)
                    messages.append({
                        'Body': message.value,
                        'ReceiptHandle': message.offset
                    })
                except StopIteration:
                    break
            return messages
        
        return await asyncio.to_thread(_dequeue)
    
    async def delete_message(
        self,
        queue_name: str,
        receipt_handle: str
    ) -> bool:
        """
        Delete a processed message from Kafka.
        Note: Kafka doesn't support explicit deletion; commits offset instead.
        """
        import asyncio
        
        def _delete():
            if self.consumer:
                self.consumer.commit()
            return True
        
        return await asyncio.to_thread(_delete)
    
    async def create_queue(
        self,
        queue_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a Kafka topic.
        Note: Topic creation typically happens via admin client or auto-creation.
        """
        # Kafka topics are often auto-created or created via admin tools
        # This is a placeholder for topic creation logic
        return True


class QStashQueue(JobQueue):
    """
    Upstash QStash implementation of JobQueue.
    Used when QUEUE_PROVIDER=upstash-qstash.
    Provides ordering guarantees for escalation timers per AQ3.
    HTTP-based client, no AWS account required.
    """
    
    def __init__(self):
        self.connection_string = QUEUE_CONNECTION_STRING
        # Import httpx only when needed
        try:
            import httpx
            # QStash uses base URL like https://qstash.upstash.io
            # Authorization header uses the token from connection string
            self.client = httpx.AsyncClient(
                base_url="https://qstash.upstash.io",
                headers={"Authorization": f"Bearer {self.connection_string}"}
            )
        except ImportError:
            raise ImportError("httpx is required for QStash queue. Install with: pip install httpx")
    
    async def enqueue(
        self,
        queue_name: str,
        job_data: Dict[str, Any],
        delay_seconds: int = 0
    ) -> str:
        """Enqueue a job to QStash."""
        import json
        
        response = await self.client.post(
            f"/v2/publish/{queue_name}",
            json={
                "body": json.dumps(job_data),
                "delay": delay_seconds
            }
        )
        response.raise_for_status()
        return response.json().get("messageId", "")
    
    async def dequeue(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20
    ) -> list:
        """Dequeue jobs from QStash."""
        import json
        
        response = await self.client.get(
            f"/v2/messages/{queue_name}",
            params={"upTo": max_messages}
        )
        response.raise_for_status()
        
        messages = response.json().get("messages", [])
        return [
            {
                'Body': json.loads(msg.get("body", "{}")),
                'ReceiptHandle': msg.get("messageId", "")
            }
            for msg in messages
        ]
    
    async def delete_message(
        self,
        queue_name: str,
        receipt_handle: str
    ) -> bool:
        """Delete a processed message from QStash."""
        try:
            response = await self.client.delete(
                f"/v2/messages/{queue_name}/{receipt_handle}"
            )
            response.raise_for_status()
            return True
        except Exception:
            return False
    
    async def create_queue(
        self,
        queue_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a QStash queue/topic.
        Note: QStash topics are auto-created on first publish.
        """
        # QStash topics are auto-created, this is a no-op
        return True


class RedisQueue(JobQueue):
    """
    Redis implementation of JobQueue using Upstash Redis.
    Used when QUEUE_PROVIDER=redis.
    Provides serverless, HTTP-based Redis connectivity.
    """
    
    def __init__(self):
        # Read connection string at init time (not import time) so env vars can be set after import
        conn_str = os.getenv("QUEUE_CONNECTION_STRING") or QUEUE_CONNECTION_STRING
        self.connection_string = self._normalize_redis_url(conn_str)
        self._closed = False
        try:
            import redis.asyncio as redis
            self.redis_client = redis.from_url(
                self.connection_string,
                encoding="utf-8",
                decode_responses=True
            )
        except ImportError:
            raise ImportError("redis is required for Redis queue. Install with: pip install redis")

    async def close(self):
        """Properly close the Redis connection pool."""
        if not self._closed and hasattr(self, 'redis_client'):
            self._closed = True
            await self.redis_client.aclose()

    @staticmethod
    def _normalize_redis_url(value: Optional[str]) -> str:
        """Accept a raw redis URL or a pasted `redis-cli ... -u <url>` command."""
        raw = (value or "").strip()
        if not raw:
            raise ValueError("QUEUE_CONNECTION_STRING is required for Redis queue")
        if raw.startswith(("redis://", "rediss://", "unix://")):
            return raw
        if "-u " in raw:
            after = raw.split("-u ", 1)[1].strip().strip("'\"")
            candidate = after.split()[0].strip("'\"")
            if candidate.startswith(("redis://", "rediss://", "unix://")):
                return candidate
        raise ValueError(
            "Redis URL must specify one of the following schemes "
            "(redis://, rediss://, unix://)"
        )
    
    async def enqueue(
        self,
        queue_name: str,
        job_data: Dict[str, Any],
        delay_seconds: int = 0
    ) -> str:
        """Enqueue a job to Redis list."""
        import json
        import uuid
        from datetime import timezone
        
        message_id = str(uuid.uuid4())
        payload = {
            "id": message_id,
            "body": job_data,
            "enqueued_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        }
        
        if delay_seconds > 0:
            # Use Redis sorted set for delayed jobs with score as timestamp
            import time
            score = time.time() + delay_seconds
            await self.redis_client.zadd(
                f"{queue_name}:delayed",
                {json.dumps(payload): score}
            )
        else:
            # Use Redis list for immediate jobs
            await self.redis_client.lpush(queue_name, json.dumps(payload))
        
        return message_id
    
    async def dequeue(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20
    ) -> list:
        """Dequeue jobs from Redis."""
        import json
        import time
        
        messages = []
        
        # First, check for delayed jobs that are ready
        current_time = time.time()
        ready_delayed = await self.redis_client.zrangebyscore(
            f"{queue_name}:delayed",
            0,
            current_time,
            start=0,
            num=max_messages
        )
        
        # Move ready delayed jobs to main queue
        for delayed_msg in ready_delayed:
            await self.redis_client.zrem(f"{queue_name}:delayed", delayed_msg)
            await self.redis_client.lpush(queue_name, delayed_msg)
        
        # Dequeue from main queue one at a time to avoid pipeline issues
        for _ in range(max_messages):
            msg = await self.redis_client.rpop(queue_name)
            if msg:
                payload = json.loads(msg)
                messages.append({
                    'Body': payload.get("body", {}),
                    'ReceiptHandle': payload.get("id", "")
                })
        
        return messages
    
    async def delete_message(
        self,
        queue_name: str,
        receipt_handle: str
    ) -> bool:
        """Delete a processed message from Redis."""
        # Redis doesn't have explicit message deletion like SQS
        # Messages are removed when dequeued. This is a no-op for idempotency.
        return True
    
    async def create_queue(
        self,
        queue_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a Redis queue/list.
        Redis lists are auto-created on first operation, this is a no-op.
        """
        return True


def get_queue() -> JobQueue:
    """
    Factory function to get the configured queue implementation.

    Reads QUEUE_PROVIDER at call time so test harnesses can override
    os.environ after import (module-level QUEUE_PROVIDER is fixed at load).

    Returns:
        JobQueue instance based on QUEUE_PROVIDER env var
    """
    provider = os.getenv("QUEUE_PROVIDER", "memory").lower()

    if provider == "memory":
        return InMemoryQueue()
    if provider == "sqs":
        return SQSQueue()
    if provider == "kafka":
        return KafkaQueue()
    if provider == "upstash-qstash":
        return QStashQueue()
    if provider == "redis":
        return RedisQueue()
    raise ValueError(f"Unsupported queue provider: {provider}")


_queue_instance: Optional[JobQueue] = None


def get_queue_instance() -> JobQueue:
    """Lazy singleton queue accessor."""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = get_queue()
    return _queue_instance


def reset_queue_instance() -> None:
    """Reset queue singleton — used in tests."""
    global _queue_instance
    if _queue_instance is not None and hasattr(_queue_instance, 'close'):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't await in a running loop; schedule for later
                loop.create_task(_queue_instance.close())
            else:
                loop.run_until_complete(_queue_instance.close())
        except RuntimeError:
            pass  # No event loop running
    _queue_instance = None


class JobRegistry:
    """
    Registry for job handlers.
    Maps job types to their handler functions.
    """
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
    
    def register(self, job_type: str, handler: Callable):
        """
        Register a job handler.
        
        Args:
            job_type: Type identifier for the job
            handler: Async function to handle the job
        """
        self.handlers[job_type] = handler
    
    async def execute(self, job_type: str, job_data: Dict[str, Any]):
        """
        Execute a job by type.
        
        Args:
            job_type: Type identifier for the job
            job_data: Job payload data
        """
        handler = self.handlers.get(job_type)
        if not handler:
            raise ValueError(f"No handler registered for job type: {job_type}")
        
        await handler(job_data)


# Global job registry
job_registry = JobRegistry()
