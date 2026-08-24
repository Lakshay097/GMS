"""
Tests for Phase 5 PostgreSQL idempotency implementation.
Verifies that idempotency keys prevent duplicate mutations and handle concurrent requests safely.
"""
import pytest
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
import json

from shared.idempotency.idempotency import (
    IdempotencyStore,
    generate_request_hash,
    cleanup_expired_keys
)


@pytest.mark.asyncio
class TestIdempotencyStore:
    """Test PostgreSQL idempotency store functionality."""

    async def test_store_and_retrieve_response(self, db: AsyncSession):
        """
        Test that idempotency keys can be stored and retrieved.
        """
        store = IdempotencyStore(db)
        
        idempotency_key = "test-key-123"
        response_data = {"id": str(uuid4()), "status": "created"}
        status_code = 201
        
        await store.store_response(
            idempotency_key=idempotency_key,
            response_data=response_data,
            status_code=status_code,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations",
            request_params_hash="abc123"
        )
        await db.commit()
        
        # Retrieve the stored response
        cached = await store.get_response(idempotency_key)
        
        assert cached is not None
        assert cached["response_data"] == response_data
        assert cached["status_code"] == status_code

    async def test_duplicate_key_handling(self, db: AsyncSession):
        """
        Test that duplicate idempotency keys are handled atomically.
        The second insert should be ignored (ON CONFLICT DO NOTHING).
        """
        store = IdempotencyStore(db)
        
        idempotency_key = "test-key-duplicate"
        response_data_1 = {"id": str(uuid4()), "status": "created"}
        response_data_2 = {"id": str(uuid4()), "status": "updated"}
        
        # First insert
        await store.store_response(
            idempotency_key=idempotency_key,
            response_data=response_data_1,
            status_code=201,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations"
        )
        await db.commit()
        
        # Second insert with same key (should be ignored)
        await store.store_response(
            idempotency_key=idempotency_key,
            response_data=response_data_2,
            status_code=200,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations"
        )
        await db.commit()
        
        # Should still return the first response
        cached = await store.get_response(idempotency_key)
        assert cached["response_data"] == response_data_1
        assert cached["status_code"] == 201

    async def test_expired_key_not_returned(self, db: AsyncSession):
        """
        Test that expired idempotency keys are not returned.
        """
        store = IdempotencyStore(db)
        
        idempotency_key = "test-key-expired"
        response_data = {"id": str(uuid4()), "status": "created"}
        
        # Manually insert an expired key
        from sqlalchemy import text
        stmt = text("""
            INSERT INTO idempotency_keys (id, key, user_id, endpoint, response_data, status_code, expires_at)
            VALUES (:id, :key, :user_id, :endpoint, :response_data, :status_code, :expires_at)
        """).bindparams(
            id=str(uuid4()),
            key=idempotency_key,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations",
            response_data=json.dumps(response_data),
            status_code=201,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)  # Expired 1 hour ago
        )
        await db.execute(stmt)
        await db.commit()
        
        # Should not return expired key
        cached = await store.get_response(idempotency_key)
        assert cached is None

    async def test_is_key_processed(self, db: AsyncSession):
        """
        Test that is_key_processed correctly identifies processed keys.
        """
        store = IdempotencyStore(db)
        
        idempotency_key = "test-key-processed"
        
        # Key not processed yet
        assert await store.is_key_processed(idempotency_key) is False
        
        # Store the key
        await store.store_response(
            idempotency_key=idempotency_key,
            response_data={"id": str(uuid4())},
            status_code=201,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations"
        )
        await db.commit()
        
        # Key should now be processed
        assert await store.is_key_processed(idempotency_key) is True

    async def test_payload_validation_match(self, db: AsyncSession):
        """
        Test that payload validation works when payloads match.
        """
        store = IdempotencyStore(db)
        
        idempotency_key = "test-key-payload-match"
        request_hash = "abc123"
        
        # Store with request hash
        await store.store_response(
            idempotency_key=idempotency_key,
            response_data={"id": str(uuid4())},
            status_code=201,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations",
            request_params_hash=request_hash
        )
        await db.commit()
        
        # Validate with same hash (should match)
        assert await store.validate_payload_match(idempotency_key, request_hash) is True

    async def test_payload_validation_mismatch(self, db: AsyncSession):
        """
        Test that payload validation detects payload mismatches.
        """
        store = IdempotencyStore(db)
        
        idempotency_key = "test-key-payload-mismatch"
        original_hash = "abc123"
        different_hash = "xyz789"
        
        # Store with original hash
        await store.store_response(
            idempotency_key=idempotency_key,
            response_data={"id": str(uuid4())},
            status_code=201,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations",
            request_params_hash=original_hash
        )
        await db.commit()
        
        # Validate with different hash (should not match)
        assert await store.validate_payload_match(idempotency_key, different_hash) is False

    async def test_cleanup_expired_keys(self, db: AsyncSession):
        """
        Test that cleanup_expired_keys removes expired keys.
        """
        store = IdempotencyStore(db)
        
        # Insert both valid and expired keys
        from sqlalchemy import text
        
        # Valid key
        await store.store_response(
            idempotency_key="valid-key",
            response_data={"id": str(uuid4())},
            status_code=201,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations"
        )
        
        # Expired key
        stmt = text("""
            INSERT INTO idempotency_keys (id, key, user_id, endpoint, response_data, status_code, expires_at)
            VALUES (:id, :key, :user_id, :endpoint, :response_data, :status_code, :expires_at)
        """).bindparams(
            id=str(uuid4()),
            key="expired-key",
            user_id=str(uuid4()),
            endpoint="/api/v1/observations",
            response_data=json.dumps({"id": str(uuid4())}),
            status_code=201,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        await db.execute(stmt)
        await db.commit()
        
        # Cleanup expired keys
        cleaned_count = await cleanup_expired_keys(db)
        
        # Should have cleaned 1 key
        assert cleaned_count >= 1
        
        # Valid key should still exist
        assert await store.is_key_processed("valid-key") is True
        
        # Expired key should not exist
        assert await store.is_key_processed("expired-key") is False


@pytest.mark.asyncio
class TestRequestHashGeneration:
    """Test request hash generation for payload validation."""

    def test_generate_request_hash_consistent(self):
        """
        Test that the same request data generates the same hash.
        """
        request_data = {
            "kpi_id": str(uuid4()),
            "value_numeric": 95.5,
            "school_id": str(uuid4())
        }
        
        hash1 = generate_request_hash(request_data)
        hash2 = generate_request_hash(request_data)
        
        assert hash1 == hash2

    def test_generate_request_hash_different_data(self):
        """
        Test that different request data generates different hashes.
        """
        request_data_1 = {"kpi_id": str(uuid4()), "value": 95.5}
        request_data_2 = {"kpi_id": str(uuid4()), "value": 85.5}
        
        hash1 = generate_request_hash(request_data_1)
        hash2 = generate_request_hash(request_data_2)
        
        assert hash1 != hash2

    def test_generate_request_hash_order_independent(self):
        """
        Test that key order doesn't affect hash generation.
        """
        request_data_1 = {"a": 1, "b": 2, "c": 3}
        request_data_2 = {"c": 3, "a": 1, "b": 2}
        
        hash1 = generate_request_hash(request_data_1)
        hash2 = generate_request_hash(request_data_2)
        
        assert hash1 == hash2


@pytest.mark.asyncio
class TestConcurrentIdempotency:
    """Test idempotency behavior under concurrent requests."""

    async def test_concurrent_same_key(self, db: AsyncSession):
        """
        Test that concurrent requests with the same idempotency key are handled safely.
        This simulates the race condition where two requests arrive simultaneously.
        """
        import asyncio
        
        store = IdempotencyStore(db)
        idempotency_key = "concurrent-test-key"
        
        async def store_response(store, key, suffix):
            await store.store_response(
                idempotency_key=key,
                response_data={"id": f"{suffix}-{str(uuid4())}"},
                status_code=201,
                user_id=str(uuid4()),
                endpoint="/api/v1/observations"
            )
        
        # Simulate concurrent requests
        await asyncio.gather(
            store_response(store, idempotency_key, "first"),
            store_response(store, idempotency_key, "second"),
            store_response(store, idempotency_key, "third")
        )
        
        await db.commit()
        
        # Only one should have been stored
        cached = await store.get_response(idempotency_key)
        assert cached is not None
        
        # The response should be from one of the requests
        # (We can't predict which one due to race conditions)
        assert "id" in cached["response_data"]


@pytest.mark.asyncio
class TestIdempotencyIntegration:
    """Integration tests for idempotency with actual endpoints."""

    async def test_observation_submission_idempotency(self, db: AsyncSession, kpi, seed_configuration):
        """
        Test that observation submission is idempotent when using idempotency keys.
        """
        from modules.observation_capture.services.observation_service import ObservationService
        from shared.idempotency.idempotency import check_idempotency, store_idempotent_response
        from decimal import Decimal
        
        service = ObservationService(db)
        idempotency_key = "obs-submission-test-key"
        
        # First request - check idempotency (should be None)
        cached = await check_idempotency(idempotency_key, db)
        assert cached is None
        
        # Submit observation
        observation = await service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Store response
        response_data = {
            "id": str(observation.id),
            "value_numeric": str(observation.value_numeric)
        }
        await store_idempotent_response(
            idempotency_key=idempotency_key,
            response_data=response_data,
            status_code=201,
            db=db,
            user_id=str(uuid4()),
            endpoint="/api/v1/observations"
        )
        await db.commit()
        
        # Second request - check idempotency (should return cached)
        cached = await check_idempotency(idempotency_key, db)
        assert cached is not None
        assert cached["response_data"] == response_data
        assert cached["status_code"] == 201
