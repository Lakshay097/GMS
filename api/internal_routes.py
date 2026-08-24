"""
Internal trigger endpoints for scheduled jobs.
These endpoints are protected and intended for Cloud Scheduler triggering.
Security: Two-factor authentication (shared secret + IP allow-listing) for defense-in-depth.
"""
import os
from datetime import datetime
from typing import Optional, List
from uuid import UUID
import ipaddress

from fastapi import APIRouter, HTTPException, Header, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db, AsyncSessionLocal
from shared.distributed_lock import with_distributed_lock
from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.checklist_scheduler.service import ChecklistScheduler
from modules.task_management.services.escalation_scheduler import TaskEscalationScheduler
# ScorecardScheduler removed in M3 (performance-scorecards module deleted)

router = APIRouter(prefix="/internal/scheduler", tags=["internal-scheduler"])

# Internal secret for Cloud Scheduler authentication
env = os.getenv("ENV", "development")
INTERNAL_SCHEDULER_SECRET = os.getenv("INTERNAL_SCHEDULER_SECRET")

if not INTERNAL_SCHEDULER_SECRET:
    if env == "production":
        raise ValueError(
            "INTERNAL_SCHEDULER_SECRET environment variable is required in production. "
            "This secret is used to authenticate Cloud Scheduler requests. "
            "Without it, internal scheduler endpoints cannot be secured."
        )
    else:
        # Use a default for development only
        INTERNAL_SCHEDULER_SECRET = "dev-secret-do-not-use-in-production"
        print("WARNING: INTERNAL_SCHEDULER_SECRET not set. Using development default.")
elif env == "production":
    # Validate against known defaults in production
    default_secrets = ["change-me-in-production", "secret", "password", "changeme", "default", "test"]
    if INTERNAL_SCHEDULER_SECRET.lower() in default_secrets:
        raise ValueError(
            "INTERNAL_SCHEDULER_SECRET must not use default values in production. "
            f"Current value '{INTERNAL_SCHEDULER_SECRET}' is insecure. "
            "Please set a strong, unique secret in your environment configuration."
        )

# IP allow-listing for Cloud Scheduler (second control layer)
# Google Cloud Scheduler egress ranges (defense-in-depth security)
CLOUD_SCHEDULER_IP_RANGES = os.getenv("CLOUD_SCHEDULER_IP_RANGES", "")
ALLOWED_IPS = [ip.strip() for ip in CLOUD_SCHEDULER_IP_RANGES.split(",") if ip.strip()] if CLOUD_SCHEDULER_IP_RANGES else []

def is_ip_allowed(client_ip: str) -> bool:
    """
    Check if client IP is in the allow-list.
    In development, allow all IPs for convenience.
    In production, require explicit allow-list.
    """
    current_env = os.getenv("ENV", "development")
    
    if current_env == "development":
        return True  # Allow all IPs in development
    
    # Reload allowed IPs from environment in case it changed
    current_ranges = os.getenv("CLOUD_SCHEDULER_IP_RANGES", "")
    current_allowed_ips = [ip.strip() for ip in current_ranges.split(",") if ip.strip()] if current_ranges else []
    
    if not current_allowed_ips:
        # In production without allow-list, fail closed for security
        return False
    
    try:
        client_addr = ipaddress.ip_address(client_ip)
        for allowed_ip in current_allowed_ips:
            try:
                network = ipaddress.ip_network(allowed_ip, strict=False)
                if client_addr in network:
                    return True
            except ValueError:
                continue
    except ValueError:
        return False
    
    return False


async def verify_internal_secret(x_scheduler_secret: Optional[str] = Header(None)):
    """Verify the internal scheduler secret for Cloud Scheduler authentication."""
    if x_scheduler_secret != INTERNAL_SCHEDULER_SECRET:
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")
    return True


async def verify_client_ip(request: Request):
    """
    Verify client IP is in the allow-list (second control layer).
    Provides defense-in-depth security beyond shared secret.
    """
    # Get client IP from request
    client_ip = request.client.host if request.client else None
    
    if not client_ip:
        raise HTTPException(status_code=403, detail="Unable to determine client IP")
    
    if not is_ip_allowed(client_ip):
        raise HTTPException(
            status_code=403, 
            detail=f"Client IP {client_ip} not in allow-list. Configure CLOUD_SCHEDULER_IP_RANGES."
        )
    return True


async def verify_internal_auth(
    x_scheduler_secret: Optional[str] = Header(None),
    request: Request = None
):
    """
    Combined verification: both secret and IP must be valid.
    Provides defense-in-depth security for internal scheduler endpoints.
    """
    # Verify shared secret
    await verify_internal_secret(x_scheduler_secret)
    
    # Verify IP allow-list (second control layer)
    await verify_client_ip(request)
    
    return True


@router.post("/compliance-check")
async def trigger_compliance_check(
    request: Request,
    x_scheduler_secret: Optional[str] = Header(None)
):
    """
    Internal endpoint to trigger compliance scheduler run.
    Protected by two-factor authentication: shared secret + IP allow-listing.
    """
    await verify_internal_auth(x_scheduler_secret, request)
    
    # Get optional parameters from request body
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    as_of = body.get("as_of")  # Optional ISO format datetime
    last_run_at = body.get("last_run_at")  # Optional ISO format datetime
    
    # Parse datetime parameters if provided
    as_of_dt = datetime.fromisoformat(as_of) if as_of else None
    last_run_dt = datetime.fromisoformat(last_run_at) if last_run_at else None
    
    async with AsyncSessionLocal() as db:
        scheduler = ComplianceScheduler(db)
        result = await scheduler.run(as_of=as_of_dt, last_run_at=last_run_dt)
    
    return {
        "status": "success",
        "run_id": str(result.run_id),
        "records_generated": result.records_generated,
        "records_backfilled": result.records_backfilled,
        "scheduler_status": result.status.value
    }


@router.post("/checklist-check")
async def trigger_checklist_check(
    request: Request,
    x_scheduler_secret: Optional[str] = Header(None)
):
    """
    Internal endpoint to trigger checklist scheduler run.
    Protected by two-factor authentication: shared secret + IP allow-listing.
    """
    await verify_internal_auth(x_scheduler_secret, request)
    
    # Get optional parameters from request body
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    school_id = body.get("school_id")  # Optional: specific school to run for
    as_of = body.get("as_of")  # Optional ISO format datetime
    
    # Parse datetime parameter if provided
    as_of_dt = datetime.fromisoformat(as_of) if as_of else None
    
    async with AsyncSessionLocal() as db:
        scheduler = ChecklistScheduler(db)
        
        if school_id:
            # Run for specific school
            school_uuid = UUID(school_id)
            results = await scheduler.run_for_school(school_uuid, as_of=as_of_dt)
        else:
            # Run for all schools (would need to iterate over schools)
            # For now, this endpoint requires school_id
            raise HTTPException(status_code=400, detail="school_id is required")
    
    return {
        "status": "success",
        "results": [
            {
                "template_id": str(r.template_id),
                "school_id": str(r.school_id),
                "department_id": str(r.department_id),
                "period_start": r.period_start.isoformat(),
                "created": r.created,
                "instance_id": str(r.instance_id) if r.instance_id else None
            }
            for r in results
        ]
    }


@router.post("/escalation-check")
async def trigger_escalation_check(
    request: Request,
    x_scheduler_secret: Optional[str] = Header(None)
):
    """
    Internal endpoint to trigger escalation scheduler check.
    Protected by two-factor authentication: shared secret + IP allow-listing.
    """
    await verify_internal_auth(x_scheduler_secret, request)
    
    # Get optional parameters from request body
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    clock_now = body.get("clock_now")  # Optional ISO format datetime for testing
    
    # Parse datetime parameter if provided
    clock_now_dt = datetime.fromisoformat(clock_now) if clock_now else None
    
    async with AsyncSessionLocal() as db:
        scheduler = TaskEscalationScheduler(db)
        result = await scheduler.run_check(clock_now=clock_now_dt)
    
    return {
        "status": "success",
        "tasks_checked": result["tasks_checked"],
        "escalations_fired": result["escalations_fired"],
        "errors": result["errors"]
    }


@router.post("/grace-period-sweep")
async def trigger_grace_period_sweep(
    request: Request,
    x_scheduler_secret: Optional[str] = Header(None)
):
    """
    Internal endpoint to trigger grace period sweep.
    Protected by two-factor authentication: shared secret + IP allow-listing.
    
    Safe for concurrent execution with Redis-based distributed locking.
    """
    await verify_internal_auth(x_scheduler_secret, request)
    
    # Get optional parameters from request body
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    as_of = body.get("as_of")  # Optional ISO format datetime
    
    # Parse datetime parameter if provided
    as_of_dt = datetime.fromisoformat(as_of) if as_of else None
    
    async with AsyncSessionLocal() as db:
        scheduler = ComplianceScheduler(db)
        closed_count = await scheduler.sweep_grace_periods(as_of=as_of_dt)
    
    if closed_count == 0:
        # Could be either no records to close, or lock already held
        return {
            "status": "skipped",
            "records_closed": 0,
            "reason": "No records to close or distributed lock already held"
        }
    
    return {
        "status": "success",
        "records_closed": closed_count
    }


# Scorecard generation endpoint removed in M3 (performance-scorecards module deleted)
# This endpoint was used to trigger scorecard generation for performance reviews
# Since the entire performance-scorecards module was removed, this endpoint is no longer needed