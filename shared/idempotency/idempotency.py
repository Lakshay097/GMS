"""
Idempotency middleware per API-Spec §5.
Ensures write operations are idempotent using idempOTency keys.
"""
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update
import hashlib
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Idempotency key expiration (default 24 hours)
IDEMPOTENCY_EXPIRY_HOURS = int(os.getenv("IDEMPOTENCY_EXPIRY_HOURS", "24"))


class IdempotencyStore:
    """
    Store for idempotency keys and their responses.
    In production, this should use Redis for distributed caching.
    For now, using database-backed storage.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def store_response(
        self,
        idempotency_key: str,
        response_data: Dict[str, Any],
        status_code: int
    ) -> None:
        """
        Store the response for an idempotency key.
        
        Args:
            idempotency_key: The idempotency key
            response_data: Response data to cache
            status_code: HTTP status code
        """
        # This will be implemented once we have the idempotency table
        # For now, this is scaffolding
        pass
    
    async def get_response(
        self,
        idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response for an idempotency key.
        
        Args:
            idempotency_key: The idempotency key
            
        Returns:
            Cached response data if exists and not expired, None otherwise
        """
        # This will be implemented once we have the idempotency table
        # For now, this is scaffolding
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


def generate_idempotency_key(request: Request) -> str:
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
    db: AsyncSession
) -> None:
    """
    Store response for an idempotency key.
    
    Args:
        idempotency_key: The idempotency key
        response_data: Response data to cache
        status_code: HTTP status code
        db: Database session
    """
    store = IdempotencyStore(db)
    await store.store_response(idempotency_key, response_data, status_code)
