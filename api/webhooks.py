"""
Clerk webhook handler for user creation and department requests.
Processes user.created events to handle self-service department requests.
"""
import os
import hmac
import hashlib
from fastapi import APIRouter, HTTPException, status, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.models import (
    User, UserStatus, Department, DepartmentRequestStatus, School
)
from shared.database import get_db
from shared.datetime_utils import utc_now


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class ClerkWebhookEvent(BaseModel):
    """Clerk webhook event model."""
    object: str
    type: str
    data: dict


class DepartmentRequestData(BaseModel):
    """Department request data from webhook payload."""
    school_code: str
    requested_department_id: Optional[str] = None
    full_name: str
    phone: Optional[str] = None


def verify_clerk_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Clerk webhook signature.
    Uses HMAC-SHA256 with CLERK_WEBHOOK_SECRET.
    """
    webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET")
    if not webhook_secret:
        # In development, you might want to skip verification
        # For production, this should be required
        if os.getenv("ENVIRONMENT") == "development":
            return True
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_WEBHOOK_SECRET not configured"
        )
    
    expected_signature = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Clerk sends signature in format: sv1=signature
    # We need to handle both formats
    if signature.startswith("sv1="):
        signature = signature[4:]
    
    return hmac.compare_digest(expected_signature, signature)


@router.post("/clerk")
async def handle_clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Clerk webhooks.
    Currently processes user.created events for department requests.
    """
    # Get raw payload for signature verification
    payload = await request.body()
    
    # Verify signature
    signature = request.headers.get("Clerk-Signature", "")
    if not verify_clerk_webhook_signature(payload, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Parse event
    try:
        event = ClerkWebhookEvent.model_validate_json(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {str(e)}"
        )
    
    # Handle user.created event
    if event.type == "user.created":
        await handle_user_created(event.data, db)
    else:
        # Acknowledge other event types but don't process
        return {"status": "acknowledged", "event_type": event.type}
    
    return {"status": "processed", "event_type": event.type}


async def handle_user_created(user_data: dict, db: AsyncSession):
    """
    Handle user.created event from Clerk.
    Creates user record and processes department request if provided.
    """
    clerk_user_id = user_data.get("id")
    email = user_data.get("email_addresses", [{}])[0].get("email_address")
    
    if not clerk_user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required user data"
        )
    
    # Check if user already exists (prevent duplicates)
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        # User already exists, skip
        return
    
    # Extract public metadata (contains our signup form data)
    public_metadata = user_data.get("public_metadata", {})
    school_code = public_metadata.get("school_code")
    requested_department_id = public_metadata.get("requested_department_id")
    full_name = public_metadata.get("full_name") or email.split("@")[0]
    phone = public_metadata.get("phone")
    
    if not school_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School code is required"
        )
    
    # Find school by code
    result = await db.execute(
        select(School).where(
            School.code == school_code,
            School.status == "active"
        )
    )
    school = result.scalar_one_or_none()
    
    if not school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school code"
        )
    
    # Create user with Viewer role
    user = User(
        clerk_user_id=clerk_user_id,
        email=email,
        full_name=full_name,
        school_id=school.id,
        department_id=None,  # Will be set by department request logic
        requested_department_id=None,
        department_request_status=DepartmentRequestStatus.NONE,
        status=UserStatus.ACTIVE,
        roles=["Viewer"],  # Default role for self-signed-up users
        mfa_enabled=False,
        phone=phone
    )
    
    # Process department request if provided
    if requested_department_id:
        # Find department
        result = await db.execute(
            select(Department).where(
                Department.id == requested_department_id,
                Department.school_id == school.id,
                Department.status == "active"
            )
        )
        department = result.scalar_one_or_none()
        
        if department:
            if department.auto_accept_requests:
                # Auto-approve
                user.department_id = department.id
                user.department_request_status = DepartmentRequestStatus.APPROVED
                user.requested_at = utc_now()
            else:
                # Pending approval
                user.requested_department_id = department.id
                user.department_request_status = DepartmentRequestStatus.PENDING
                user.requested_at = utc_now()
        else:
            # Invalid department ID, skip department assignment
            user.department_request_status = DepartmentRequestStatus.NONE
    
    db.add(user)
    await db.commit()
