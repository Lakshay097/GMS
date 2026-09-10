"""
Expiration Reminder API routes — CRUD for ExpirationRecord entities.
Handles creation, listing, renewal, and deletion of expirable items.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.middleware.tenancy import require_tenant_context, TenantContext
from modules.expiration_reminder.services.expiration_service import ExpirationService

router = APIRouter(prefix="/expiration-records", tags=["expiration-records"])


def _is_superadmin(tenant_context: TenantContext) -> bool:
    return "superadmin" in [r.lower() for r in tenant_context.roles]


def _can_access(tenant_context: TenantContext, record_school_id) -> bool:
    """SuperAdmin sees all schools; everyone else must match their own."""
    if _is_superadmin(tenant_context):
        return True
    return tenant_context.school_id is not None and str(record_school_id) == tenant_context.school_id


# ── Schemas ─────────────────────────────────────────────────────────────────

class ExpirationRecordCreate(BaseModel):
    entity_type: str = Field(..., description="certificate|license|lease|insurance|permit|calibration|training|other")
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    document_reference: Optional[str] = None
    entity_id: Optional[str] = None
    entity_link: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: datetime
    renew_by_at: Optional[datetime] = None
    reminder_lead_days: int = Field(default=30, ge=0, le=365)
    department_id: Optional[str] = None
    metadata_json: Optional[dict] = None


class ExpirationRecordUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    expires_at: Optional[datetime] = None
    renew_by_at: Optional[datetime] = None
    reminder_lead_days: Optional[int] = None
    entity_type: Optional[str] = None
    document_reference: Optional[str] = None
    entity_link: Optional[str] = None


class RenewRequest(BaseModel):
    new_expires_at: datetime


def _serialize(record) -> dict:
    return {
        "id": str(record.id),
        "school_id": str(record.school_id),
        "department_id": str(record.department_id) if record.department_id else None,
        "created_by": str(record.created_by) if record.created_by else None,
        "entity_type": record.entity_type.value if hasattr(record.entity_type, "value") else record.entity_type,
        "title": record.title,
        "description": record.description,
        "document_reference": record.document_reference,
        "entity_id": str(record.entity_id) if record.entity_id else None,
        "entity_link": record.entity_link,
        "issued_at": record.issued_at.isoformat() if record.issued_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "renewed_at": record.renewed_at.isoformat() if record.renewed_at else None,
        "renew_by_at": record.renew_by_at.isoformat() if record.renew_by_at else None,
        "status": record.status.value if hasattr(record.status, "value") else record.status,
        "reminder_lead_days": record.reminder_lead_days,
        "reminder_sent_at": record.reminder_sent_at.isoformat() if record.reminder_sent_at else None,
        "is_acknowledged": record.is_acknowledged,
        "metadata_json": record.metadata_json,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


# ── Routes ──────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_expiration_record(
    body: ExpirationRecordCreate,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    from shared.platform_models import ExpirationEntityType

    if not tenant_context.school_id:
        raise HTTPException(status_code=400, detail="School context required")

    # Validate entity_type
    try:
        entity_type = ExpirationEntityType(body.entity_type)
    except ValueError:
        valid = [e.value for e in ExpirationEntityType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type. Valid: {valid}",
        )

    if body.expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="expires_at must be in the future",
        )

    service = ExpirationService(db)
    record = await service.create_record(
        school_id=UUID(tenant_context.school_id),
        department_id=UUID(body.department_id) if body.department_id else None,
        created_by=UUID(tenant_context.user_id),
        entity_type=entity_type,
        title=body.title,
        description=body.description,
        document_reference=body.document_reference,
        entity_id=UUID(body.entity_id) if body.entity_id else None,
        entity_link=body.entity_link,
        issued_at=body.issued_at,
        expires_at=body.expires_at,
        renew_by_at=body.renew_by_at,
        reminder_lead_days=body.reminder_lead_days,
        metadata_json=body.metadata_json,
    )
    await db.commit()
    return _serialize(record)


@router.get("")
async def list_expiration_records(
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    entity_type: Optional[str] = None,
    department_id: Optional[str] = None,
    expiring_within_days: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    from shared.platform_models import ExpirationStatus, ExpirationEntityType

    if not tenant_context.school_id and not _is_superadmin(tenant_context):
        raise HTTPException(status_code=400, detail="School context required")

    status_enum = None
    if status_filter:
        try:
            status_enum = ExpirationStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}")

    entity_type_enum = None
    if entity_type:
        try:
            entity_type_enum = ExpirationEntityType(entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity_type: {entity_type}")

    service = ExpirationService(db)
    records, total = await service.list_records(
        school_id=UUID(tenant_context.school_id) if tenant_context.school_id else None,
        status=status_enum,
        entity_type=entity_type_enum,
        department_id=UUID(department_id) if department_id else None,
        expiring_within_days=expiring_within_days,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_serialize(r) for r in records],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/summary")
async def get_reminder_summary(
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard widget summary — counts by urgency tier."""
    if not tenant_context.school_id and not _is_superadmin(tenant_context):
        raise HTTPException(status_code=400, detail="School context required")

    service = ExpirationService(db)
    return await service.get_reminder_summary(
        school_id=UUID(tenant_context.school_id) if tenant_context.school_id else None
    )


@router.get("/expiring-soon")
async def get_expiring_soon(
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    days_ahead: int = Query(30, ge=1, le=365),
):
    """All records expiring within N days (active + expiring_soon)."""
    if not tenant_context.school_id and not _is_superadmin(tenant_context):
        raise HTTPException(status_code=400, detail="School context required")

    service = ExpirationService(db)
    records = await service.get_expiring_soon(
        school_id=UUID(tenant_context.school_id) if tenant_context.school_id else None,
        days_ahead=days_ahead,
    )
    return [_serialize(r) for r in records]


@router.get("/{record_id}")
async def get_expiration_record(
    record_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    service = ExpirationService(db)
    record = await service.get_record(record_id)
    if record is None or not _can_access(tenant_context, record.school_id):
        raise HTTPException(status_code=404, detail="Record not found")
    return _serialize(record)


@router.patch("/{record_id}")
async def update_expiration_record(
    record_id: UUID,
    body: ExpirationRecordUpdate,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    from shared.platform_models import ExpirationEntityType

    service = ExpirationService(db)
    record = await service.get_record(record_id)
    if record is None or not _can_access(tenant_context, record.school_id):
        raise HTTPException(status_code=404, detail="Record not found")

    entity_type_enum = None
    if body.entity_type:
        try:
            entity_type_enum = ExpirationEntityType(body.entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity_type: {body.entity_type}")

    updated = await service.update_record(
        record_id=record_id,
        title=body.title,
        description=body.description,
        expires_at=body.expires_at,
        reminder_lead_days=body.reminder_lead_days,
        entity_type=entity_type_enum,
        document_reference=body.document_reference,
        entity_link=body.entity_link,
        renew_by_at=body.renew_by_at,
    )
    await db.commit()
    return _serialize(updated)


@router.post("/{record_id}/renew")
async def renew_expiration_record(
    record_id: UUID,
    body: RenewRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Mark a record as renewed with a new expiry date."""
    service = ExpirationService(db)
    record = await service.get_record(record_id)
    if record is None or not _can_access(tenant_context, record.school_id):
        raise HTTPException(status_code=404, detail="Record not found")

    if body.new_expires_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="new_expires_at must be in the future")

    renewed = await service.renew_record(
        record_id=record_id,
        new_expires_at=body.new_expires_at,
    )
    await db.commit()
    return _serialize(renewed)


@router.post("/{record_id}/acknowledge")
async def acknowledge_expiration_record(
    record_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    service = ExpirationService(db)
    record = await service.get_record(record_id)
    if record is None or not _can_access(tenant_context, record.school_id):
        raise HTTPException(status_code=404, detail="Record not found")

    acknowledged = await service.acknowledge_record(record_id)
    await db.commit()
    return _serialize(acknowledged)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expiration_record(
    record_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    service = ExpirationService(db)
    record = await service.get_record(record_id)
    if record is None or not _can_access(tenant_context, record.school_id):
        raise HTTPException(status_code=404, detail="Record not found")

    await service.delete_record(record_id)
    await db.commit()
    return None
