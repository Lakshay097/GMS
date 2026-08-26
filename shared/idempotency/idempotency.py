"""
Idempotency middleware per API-Spec §5.
Ensures write operations are idempotent using idempotency keys.
PostgreSQL-based implementation with atomic transactions.
"""
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
import hashlib
import json
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

# Idempotency key expiration (default 24 hours)
IDEMPOTENCY_EXPIRY_HOURS = int(os.getenv("IDEMPOTENCY_EXPIRY_HOURS", "24"))


class IdempotencyStore:
    """
    PostgreSQL-backed store for idempotency keys and their responses.
    Uses database constraints and transactions for atomic idempotency.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def store_response(
        self,
        idempotency_key: str,
        response_data: Dict[str, Any],
        status_code: int,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_params_hash: Optional[str] = None
    ) -> None:
        """
        Store the response for an idempotency key using atomic insert.
        
        Args:
            idempotency_key: The idempotency key
            response_data: Response data to cache
            status_code: HTTP status code
            user_id: Optional user ID for tracking
            endpoint: The endpoint that was called
            request_params_hash: Hash of request parameters for payload validation
        """
        expires_at = datetime.now(timezone.utc) + timedelta(hours=IDEMPOTENCY_EXPIRY_HOURS)
        
        # Use raw SQL with ON CONFLICT for atomic insert-or-ignore
        # This ensures concurrent requests with the same key don't create duplicates
        stmt = text("""
            INSERT INTO idempotency_keys (id, key, user_id, endpoint, request_params_hash, response_data, status_code, expires_at)
            VALUES (:id, :key, :user_id, :endpoint, :request_params_hash, :response_data, :status_code, :expires_at)
            ON CONFLICT (key) DO NOTHING
        """).bindparams(
            id=str(uuid4()),
            key=idempotency_key,
            user_id=user_id,
            endpoint=endpoint or "",
            request_params_hash=request_params_hash,
            response_data=json.dumps(response_data),
            status_code=status_code,
            expires_at=expires_at
        )
        
        await self.db.execute(stmt)
    
    async def get_response(
        self,
        idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response for an idempotency key if not expired.
        
        Args:
            idempotency_key: The idempotency key
            
        Returns:
            Cached response data if exists and not expired, None otherwise
        """
        from sqlalchemy import and_, text
        
        stmt = text("""
            SELECT response_data, status_code 
            FROM idempotency_keys 
            WHERE key = :key AND expires_at > NOW()
        """).bindparams(key=idempotency_key)
        
        result = await self.db.execute(stmt)
        row = result.fetchone()
        
        if row:
            return {
                "response_data": row[0],
                "status_code": row[1]
            }
        return None
    
    async def is_key_processed(self, idempotency_key: str) -> bool:
        """
        Check if an idempotency key has already been processed.
        
        Args:
            idempotency_key: The idempotency key
            
        Returns:
            True if key exists and is not expired, False otherwise
        """
        response = await self.get_response(idempotency_key)
        return response is not None
    
    async def validate_payload_match(
        self,
        idempotency_key: str,
        request_params_hash: str
    ) -> bool:
        """
        Validate that the current request payload matches the original.
        Prevents reuse of idempotency keys with different payloads.
        
        Args:
            idempotency_key: The idempotency key
            request_params_hash: Hash of current request parameters
            
        Returns:
            True if payload matches or key doesn't exist, False if mismatch
        """
        stmt = text("""
            SELECT request_params_hash 
            FROM idempotency_keys 
            WHERE key = :key AND expires_at > NOW()
        """).bindparams(key=idempotency_key)
        
        result = await self.db.execute(stmt)
        row = result.fetchone()
        
        if not row:
            return True  # Key doesn't exist, no mismatch
        
        # If request_params_hash was stored, validate it matches
        stored_hash = row[0]
        if stored_hash and stored_hash != request_params_hash:
            return False
        
        return True


async def generate_idempotency_key(request: Request) -> str:
    """
    Generate an idempotency key from request data.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Hash-based idempotency key
    """
    # Get the idempotency key from header if provided
    idempotency_key = request.headers.get("Idempotency-Key")
    
    if idempotency_key:
        return idempotency_key
    
    # Otherwise, generate from request method, path, and body
    method = request.method
    path = request.url.path
    
    # Read body for POST/PUT/PATCH
    body = ""
    if method in ["POST", "PUT", "PATCH"]:
        body_bytes = await request.body()
        body = body_bytes.decode("utf-8")
    
    # Create hash
    key_string = f"{method}:{path}:{body}"
    return hashlib.sha256(key_string.encode()).hexdigest()


def require_idempotency_key(request: Request) -> str:
    """
    Dependency to require idempotency key for write operations.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Idempotency key
        
    Raises:
        HTTPException if key is missing for write operations
    """
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        idempotency_key = request.headers.get("Idempotency-Key")
        
        if not idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Idempotency-Key header is required for write operations",
                        "field": "Idempotency-Key"
                    }
                }
            )
        
        return idempotency_key
    
    # For GET requests, idempotency is not required
    return ""


async def check_idempotency(
    idempotency_key: str,
    db: AsyncSession
) -> Optional[Dict[str, Any]]:
    """
    Check if an idempotency key has been processed and return cached response.
    
    Args:
        idempotency_key: The idempotency key
        db: Database session
        
    Returns:
        Cached response if exists, None otherwise
    """
    store = IdempotencyStore(db)
    return await store.get_response(idempotency_key)


async def store_idempotent_response(
    idempotency_key: str,
    response_data: Dict[str, Any],
    status_code: int,
    db: AsyncSession,
    user_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    request_params_hash: Optional[str] = None
) -> None:
    """
    Store response for an idempotency key.
    
    Args:
        idempotency_key: The idempotency key
        response_data: Response data to cache
        status_code: HTTP status code
        db: Database session
        user_id: Optional user ID for tracking
        endpoint: The endpoint that was called
        request_params_hash: Hash of request parameters for payload validation
    """
    store = IdempotencyStore(db)
    await store.store_response(
        idempotency_key, 
        response_data, 
        status_code,
        user_id=user_id,
        endpoint=endpoint,
        request_params_hash=request_params_hash
    )


def generate_request_hash(request_data: Dict[str, Any]) -> str:
    """
    Generate a hash of request parameters for payload validation.
    
    Args:
        request_data: Dictionary of request parameters
        
    Returns:
        SHA256 hash of the normalized request data
    """
    # Normalize the data to ensure consistent hashing
    normalized = json.dumps(request_data, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


async def cleanup_expired_keys(db: AsyncSession) -> int:
    """
    Clean up expired idempotency keys.
    Should be run periodically (e.g., via scheduled job).
    
    Args:
        db: Database session
        
    Returns:
        Number of keys cleaned up
    """
    stmt = text("""
        DELETE FROM idempotency_keys 
        WHERE expires_at <= NOW()
    """)
    
    result = await db.execute(stmt)
    await db.commit()
    
    return result.rowcount
