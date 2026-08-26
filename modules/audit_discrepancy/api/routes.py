"""
Audit Discrepancy API routes per PRS §21.
Provides endpoints for approval chain configuration and discrepancy management.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from shared.database import get_db
from shared.errors import ValidationError as ServiceValidationError
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.middleware.tenancy import require_tenant_context, apply_tenant_filter
from shared.platform_models import DiscrepancyApprovalChainConfig
from modules.audit_discrepancy.services.approval_chain_service import ApprovalChainService
from modules.audit_discrepancy.services.discrepancy_service import DiscrepancyService
from platform_services.workflow_engine.service import WorkflowEngine

router = APIRouter(prefix="/audit-discrepancy", tags=["audit-discrepancy"])

# Rate limiter for audit discrepancy endpoints (H3 security fix)
limiter = Limiter(key_func=get_remote_address)


# ── Schemas ──────────────────────────────────────────────────────────────

class ApprovalLevelCreate(BaseModel):
    level: int = Field(..., description="Approval level number (1-based)")
    role_id: Optional[str] = Field(None, description="Role name (e.g., 'admin', 'checker'). Use this OR user_id.")
    user_id: Optional[str] = Field(None, description="Specific user UUID. Use this OR role_id.")
    auto_escalation_sla_hours: Optional[int] = Field(None, description="Auto-escalation SLA in hours")


class ApprovalChainCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Chain name (e.g., 'Financial Audit Chain')")
    description: Optional[str] = Field(None, description="Description of when to use this chain")
    levels: List[ApprovalLevelCreate] = Field(..., description="Ordered list of approval levels")
    priority: int = Field(0, description="Higher = checked first when multiple active chains match")
    school_id: Optional[UUID] = Field(None, description="Scope to specific school (null = all schools)")
    department_id: Optional[UUID] = Field(None, description="Scope to specific department (null = all departments)")
    category_id: Optional[UUID] = Field(None, description="Scope to specific discrepancy category (null = all categories)")


class ApprovalChainUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    levels: Optional[List[ApprovalLevelCreate]] = None
    priority: Optional[int] = None
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class ApprovalChainResponse(BaseModel):
    chain_version_id: UUID
    name: str
    description: Optional[str]
    levels: List[dict]
    is_active: bool
    priority: int
    school_id: Optional[UUID]
    school_name: Optional[str] = None
    department_id: Optional[UUID]
    department_name: Optional[str] = None
    category_id: Optional[UUID]
    category_name: Optional[str] = None
    created_at: str
    created_by: Optional[UUID]


class ApprovalChainActivate(BaseModel):
    chain_version_id: UUID


# ── Discrepancy Schemas ─────────────────────────────────────────────────────

class DiscrepancyCreate(BaseModel):
    observation_id: UUID = Field(..., description="ID of the observation this discrepancy is raised against")
    category_id: UUID = Field(..., description="ID of the discrepancy category")
    school_id: UUID = Field(..., description="School ID")
    department_id: Optional[UUID] = Field(None, description="Department ID")
    raised_by_user_id: UUID = Field(..., description="ID of the user raising the discrepancy")
    description: Optional[str] = Field(None, description="Description of the discrepancy")


class DiscrepancyResponse(BaseModel):
    id: UUID
    observation_id: UUID
    category_id: UUID
    school_id: UUID
    department_id: Optional[UUID]
    raised_by_user_id: UUID
    investigation_owner_id: Optional[UUID]
    state: str
    investigation_findings: Optional[str]
    bound_chain_version_id: Optional[UUID]
    raised_at: str
    under_investigation_at: Optional[str]
    resolved_at: Optional[str]
    closed_at: Optional[str]
    created_at: str
    updated_at: str


class DiscrepancyAssignInvestigation(BaseModel):
    investigation_owner_id: UUID = Field(..., description="ID of the user assigned to investigate")


class DiscrepancySubmitFindings(BaseModel):
    investigation_findings: str = Field(..., description="Investigation findings (required before moving to Resolved)")


class DiscrepancyApprove(BaseModel):
    level: int = Field(..., description="Approval level (1, 2, 3, ...)")
    approver_id: UUID = Field(..., description="ID of the user approving this level")
    comments: Optional[str] = Field(None, description="Approval comments")


class DiscrepancyReject(BaseModel):
    level: int = Field(..., description="Approval level being rejected")
    rejecter_id: UUID = Field(..., description="ID of the user rejecting this level")
    comments: Optional[str] = Field(None, description="Rejection comments")


class DiscrepancyApprovalHistoryResponse(BaseModel):
    id: UUID
    discrepancy_id: UUID
    level: int
    assigned_role_id: Optional[UUID]
    approved_by_user_id: Optional[UUID]
    status: str
    comments: Optional[str]
    approved_at: Optional[str]
    created_at: str


# ── Dependency Injection ──────────────────────────────────────────────────

def get_approval_chain_service(
    db: AsyncSession = Depends(get_db),
) -> ApprovalChainService:
    """Dependency to get ApprovalChainService instance."""
    workflow_engine = WorkflowEngine(db)
    return ApprovalChainService(db, workflow_engine)


def get_discrepancy_service(
    db: AsyncSession = Depends(get_db),
) -> DiscrepancyService:
    """Dependency to get DiscrepancyService instance."""
    workflow_engine = WorkflowEngine(db)
    return DiscrepancyService(db, workflow_engine)


def _chain_to_response(chain: DiscrepancyApprovalChainConfig) -> ApprovalChainResponse:
    """Convert a chain model to response, resolving related names."""
    return ApprovalChainResponse(
        chain_version_id=chain.chain_version_id,
        name=chain.name,
        description=chain.description,
        levels=chain.levels,
        is_active=chain.is_active,
        priority=chain.priority,
        school_id=chain.school_id,
        school_name=chain.school.name if chain.school else None,
        department_id=chain.department_id,
        department_name=chain.department.name if chain.department else None,
        category_id=chain.category_id,
        category_name=chain.category.name if chain.category else None,
        created_at=chain.created_at.isoformat(),
        created_by=chain.created_by,
    )


# ── Approval Chain Endpoints ───────────────────────────────────────────────

@router.post("/approval-chains", response_model=ApprovalChainResponse, status_code=status.HTTP_201_CREATED)
async def create_approval_chain(
    chain: ApprovalChainCreate,
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """
    Create a new approval chain.
    Multiple chains can be active simultaneously (v2.0).
    """
    try:
        levels = [level.dict() for level in chain.levels]
        result = await service.create_approval_chain(
            levels=levels,
            name=chain.name,
            description=chain.description,
            priority=chain.priority,
            school_id=chain.school_id,
            department_id=chain.department_id,
            category_id=chain.category_id,
            created_by=UUID(tenant_context.user_id),
        )
        return _chain_to_response(result)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/approval-chains/active", response_model=ApprovalChainResponse)
async def get_active_approval_chain(
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """Get the highest-priority active approval chain."""
    result = await service.get_active_approval_chain()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active approval chain found")
    return _chain_to_response(result)


@router.get("/approval-chains", response_model=List[ApprovalChainResponse])
async def list_approval_chains(
    active_only: bool = False,
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """List all approval chains, ordered by priority."""
    chains = await service.list_approval_chains(active_only=active_only)
    return [_chain_to_response(chain) for chain in chains]


@router.get("/approval-chains/{chain_version_id}", response_model=ApprovalChainResponse)
async def get_approval_chain(
    chain_version_id: UUID,
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """Get a specific approval chain by ID."""
    result = await service.get_approval_chain(chain_version_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval chain not found")
    return _chain_to_response(result)


@router.patch("/approval-chains/{chain_version_id}", response_model=ApprovalChainResponse)
async def update_approval_chain(
    chain_version_id: UUID,
    update: ApprovalChainUpdate,
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """Update an approval chain's name, scope, priority, or levels."""
    try:
        update_data = update.dict(exclude_unset=True)
        # Handle is_active separately
        is_active = update_data.pop("is_active", None)
        levels = update_data.pop("levels", None)
        if levels is not None:
            levels = [level.dict() for level in levels]
        result = await service.update_approval_chain(
            chain_version_id=chain_version_id,
            levels=levels,
            **update_data,
        )
        if is_active is not None:
            if is_active:
                result = await service.activate_chain(chain_version_id)
            else:
                result = await service.deactivate_chain(chain_version_id)
        return _chain_to_response(result)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/approval-chains/{chain_version_id}/activate", response_model=ApprovalChainResponse)
async def activate_approval_chain(
    chain_version_id: UUID,
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """Activate an approval chain (multiple can be active in v2.0)."""
    try:
        result = await service.activate_chain(chain_version_id)
        return _chain_to_response(result)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/approval-chains/{chain_version_id}/deactivate", response_model=ApprovalChainResponse)
async def deactivate_approval_chain(
    chain_version_id: UUID,
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """Deactivate an approval chain."""
    try:
        result = await service.deactivate_chain(chain_version_id)
        return _chain_to_response(result)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/approval-chains/{chain_version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_approval_chain(
    chain_version_id: UUID,
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """Delete an approval chain (fails if bound to in-flight discrepancies)."""
    try:
        await service.delete_chain(chain_version_id)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/approval-chains/active/levels")
async def get_current_approval_levels(
    tenant_context = Depends(require_tenant_context),
    service: ApprovalChainService = Depends(get_approval_chain_service),
):
    """Get the current approval levels from the highest-priority active chain."""
    chain = await service.get_active_approval_chain()
    if not chain:
        return []
    return [
        {
            "level": level["level"],
            "role_id": level.get("role_id"),
            "user_id": level.get("user_id"),
            "assignee_type": level.get("assignee_type", "role"),
            "auto_escalation_sla_hours": level.get("auto_escalation_sla_hours"),
        }
        for level in chain.levels
    ]


# ── Discrepancy Endpoints ───────────────────────────────────────────────────

@router.get("/discrepancies", response_model=List[DiscrepancyResponse])
async def list_discrepancies(
    tenant_context = Depends(require_tenant_context),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page (max 100)"),
    service: DiscrepancyService = Depends(get_discrepancy_service),
):
    """List discrepancies with tenant isolation and pagination (per R-02)"""
    from sqlalchemy import select as sa_select
    from shared.platform_models import Discrepancy
    
    # Build base query with tenant isolation
    query = sa_select(Discrepancy).order_by(Discrepancy.created_at.desc())
    query = apply_tenant_filter(query, tenant_context)
    
    # Apply pagination at database level using LIMIT/OFFSET
    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)
    
    result = await service.db.execute(query)
    discrepancies = result.scalars().all()
    
    return [
        DiscrepancyResponse(
            id=d.id,
            observation_id=d.observation_id,
            category_id=d.category_id,
            school_id=d.school_id,
            department_id=d.department_id,
            raised_by_user_id=d.raised_by_user_id,
            investigation_owner_id=d.investigation_owner_id,
            state=d.state,
            investigation_findings=d.investigation_findings,
            bound_chain_version_id=d.bound_chain_version_id,
            raised_at=d.raised_at.isoformat() if d.raised_at else None,
            under_investigation_at=d.under_investigation_at.isoformat() if d.under_investigation_at else None,
            resolved_at=d.resolved_at.isoformat() if d.resolved_at else None,
            closed_at=d.closed_at.isoformat() if d.closed_at else None,
            created_at=d.created_at.isoformat() if d.created_at else None,
            updated_at=d.updated_at.isoformat() if d.updated_at else None,
        )
        for d in discrepancies
    ]


@router.post("/discrepancies", response_model=DiscrepancyResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")  # Rate limit discrepancy creation
async def raise_discrepancy(
    request: Request,
    discrepancy: DiscrepancyCreate,
    tenant_context = Depends(require_tenant_context),
    service: DiscrepancyService = Depends(get_discrepancy_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Raise a discrepancy against an observation.
    Auditors never edit Observations — they may only Verify or raise a Discrepancy (R-24/BR-12/C5).
    """
    # Matrix-driven permission check per R-48 (replaces hardcoded role checks)
    await PermissionChecker.require_permission(Module.DISCREPANCY, Action.RAISE, tenant_context, db)
    # SECURITY: Validate school_id matches tenant scope (prevent cross-tenant manipulation)
    if str(discrepancy.school_id) != tenant_context.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Cannot raise discrepancy for another school"}}
        )
    # SECURITY: Override raised_by_user_id with authenticated user (prevent impersonation)
    try:
        result = await service.raise_discrepancy(
            observation_id=discrepancy.observation_id,
            category_id=discrepancy.category_id,
            school_id=discrepancy.school_id,
            department_id=discrepancy.department_id,
            raised_by_user_id=UUID(tenant_context.user_id),
            description=discrepancy.description,
        )
        return DiscrepancyResponse(
            id=result.id,
            observation_id=result.observation_id,
            category_id=result.category_id,
            school_id=result.school_id,
            department_id=result.department_id,
            raised_by_user_id=result.raised_by_user_id,
            investigation_owner_id=result.investigation_owner_id,
            state=result.state,
            investigation_findings=result.investigation_findings,
            bound_chain_version_id=result.bound_chain_version_id,
            raised_at=result.raised_at.isoformat() if result.raised_at else None,
            under_investigation_at=result.under_investigation_at.isoformat() if result.under_investigation_at else None,
            resolved_at=result.resolved_at.isoformat() if result.resolved_at else None,
            closed_at=result.closed_at.isoformat() if result.closed_at else None,
            created_at=result.created_at.isoformat() if result.created_at else None,
            updated_at=result.updated_at.isoformat() if result.updated_at else None,
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/discrepancies/{discrepancy_id}/assign-investigation", response_model=DiscrepancyResponse)
@limiter.limit("30/minute")  # Rate limit investigation assignment
async def assign_investigation(
    request: Request,
    discrepancy_id: UUID,
    assignment: DiscrepancyAssignInvestigation,
    tenant_context = Depends(require_tenant_context),
    service: DiscrepancyService = Depends(get_discrepancy_service),
    db: AsyncSession = Depends(get_db),
):
    """Assign investigation owner and move to Under Investigation state."""
    # Matrix-driven permission check per R-48 (replaces hardcoded role checks)
    await PermissionChecker.require_permission(Module.DISCREPANCY, Action.INVESTIGATE, tenant_context, db)
    try:
        result = await service.assign_investigation(
            discrepancy_id=discrepancy_id,
            investigation_owner_id=assignment.investigation_owner_id,
        )
        return DiscrepancyResponse(
            id=result.id,
            observation_id=result.observation_id,
            category_id=result.category_id,
            school_id=result.school_id,
            department_id=result.department_id,
            raised_by_user_id=result.raised_by_user_id,
            investigation_owner_id=result.investigation_owner_id,
            state=result.state,
            investigation_findings=result.investigation_findings,
            bound_chain_version_id=result.bound_chain_version_id,
            raised_at=result.raised_at.isoformat() if result.raised_at else None,
            under_investigation_at=result.under_investigation_at.isoformat() if result.under_investigation_at else None,
            resolved_at=result.resolved_at.isoformat() if result.resolved_at else None,
            closed_at=result.closed_at.isoformat() if result.closed_at else None,
            created_at=result.created_at.isoformat() if result.created_at else None,
            updated_at=result.updated_at.isoformat() if result.updated_at else None,
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/discrepancies/{discrepancy_id}/submit-findings", response_model=DiscrepancyResponse)
@limiter.limit("30/minute")  # Rate limit findings submission
async def submit_investigation_findings(
    request: Request,
    discrepancy_id: UUID,
    findings: DiscrepancySubmitFindings,
    tenant_context = Depends(require_tenant_context),
    service: DiscrepancyService = Depends(get_discrepancy_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit investigation findings and move to Resolved state.
    Investigation findings are required before moving to Resolved (R-26, PRS §52).
    """
    # Matrix-driven permission check per R-48 (replaces hardcoded role checks)
    await PermissionChecker.require_permission(Module.DISCREPANCY, Action.INVESTIGATE, tenant_context, db)
    try:
        result = await service.submit_investigation_findings(
            discrepancy_id=discrepancy_id,
            investigation_findings=findings.investigation_findings,
        )
        return DiscrepancyResponse(
            id=result.id,
            observation_id=result.observation_id,
            category_id=result.category_id,
            school_id=result.school_id,
            department_id=result.department_id,
            raised_by_user_id=result.raised_by_user_id,
            investigation_owner_id=result.investigation_owner_id,
            state=result.state,
            investigation_findings=result.investigation_findings,
            bound_chain_version_id=result.bound_chain_version_id,
            raised_at=result.raised_at.isoformat() if result.raised_at else None,
            under_investigation_at=result.under_investigation_at.isoformat() if result.under_investigation_at else None,
            resolved_at=result.resolved_at.isoformat() if result.resolved_at else None,
            closed_at=result.closed_at.isoformat() if result.closed_at else None,
            created_at=result.created_at.isoformat() if result.created_at else None,
            updated_at=result.updated_at.isoformat() if result.updated_at else None,
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/discrepancies/{discrepancy_id}/start-approval", response_model=DiscrepancyResponse)
@limiter.limit("30/minute")  # Rate limit approval start
async def start_approval(
    request: Request,
    discrepancy_id: UUID,
    tenant_context = Depends(require_tenant_context),
    service: DiscrepancyService = Depends(get_discrepancy_service),
):
    """
    Start approval process by moving to Pending Approval Level 1.
    Binds the discrepancy to the current approval chain version (FR-235).
    """
    try:
        result = await service.start_approval(discrepancy_id=discrepancy_id)
        return DiscrepancyResponse(
            id=result.id,
            observation_id=result.observation_id,
            category_id=result.category_id,
            school_id=result.school_id,
            department_id=result.department_id,
            raised_by_user_id=result.raised_by_user_id,
            investigation_owner_id=result.investigation_owner_id,
            state=result.state,
            investigation_findings=result.investigation_findings,
            bound_chain_version_id=result.bound_chain_version_id,
            raised_at=result.raised_at.isoformat() if result.raised_at else None,
            under_investigation_at=result.under_investigation_at.isoformat() if result.under_investigation_at else None,
            resolved_at=result.resolved_at.isoformat() if result.resolved_at else None,
            closed_at=result.closed_at.isoformat() if result.closed_at else None,
            created_at=result.created_at.isoformat() if result.created_at else None,
            updated_at=result.updated_at.isoformat() if result.updated_at else None,
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/discrepancies/{discrepancy_id}/approve", response_model=DiscrepancyResponse)
@limiter.limit("30/minute")  # Rate limit approval actions
async def approve_discrepancy(
    request: Request,
    discrepancy_id: UUID,
    approval: DiscrepancyApprove,
    tenant_context = Depends(require_tenant_context),
    service: DiscrepancyService = Depends(get_discrepancy_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve discrepancy at a specific level.
    Enforces segregation of duties: approver cannot be investigation owner or prior approver (R-27/R-49).
    """
    # Matrix-driven permission check per R-48 (replaces hardcoded role checks)
    await PermissionChecker.require_permission(Module.DISCREPANCY, Action.APPROVE, tenant_context, db)
    # SECURITY: Override approver_id with authenticated user (prevent impersonation)
    try:
        result = await service.approve_discrepancy(
            discrepancy_id=discrepancy_id,
            level=approval.level,
            approver_id=UUID(tenant_context.user_id),
            comments=approval.comments,
        )
        return DiscrepancyResponse(
            id=result.id,
            observation_id=result.observation_id,
            category_id=result.category_id,
            school_id=result.school_id,
            department_id=result.department_id,
            raised_by_user_id=result.raised_by_user_id,
            investigation_owner_id=result.investigation_owner_id,
            state=result.state,
            investigation_findings=result.investigation_findings,
            bound_chain_version_id=result.bound_chain_version_id,
            raised_at=result.raised_at.isoformat() if result.raised_at else None,
            under_investigation_at=result.under_investigation_at.isoformat() if result.under_investigation_at else None,
            resolved_at=result.resolved_at.isoformat() if result.resolved_at else None,
            closed_at=result.closed_at.isoformat() if result.closed_at else None,
            created_at=result.created_at.isoformat() if result.created_at else None,
            updated_at=result.updated_at.isoformat() if result.updated_at else None,
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/discrepancies/{discrepancy_id}/reject", response_model=DiscrepancyResponse)
@limiter.limit("30/minute")  # Rate limit rejection actions
async def reject_discrepancy(
    request: Request,
    discrepancy_id: UUID,
    rejection: DiscrepancyReject,
    tenant_context = Depends(require_tenant_context),
    service: DiscrepancyService = Depends(get_discrepancy_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject discrepancy at a specific level.
    Rejection reopens to Under Investigation, preserving prior investigation notes.
    """
    # Matrix-driven permission check per R-48 (replaces hardcoded role checks)
    await PermissionChecker.require_permission(Module.DISCREPANCY, Action.APPROVE, tenant_context, db)
    # SECURITY: Override rejecter_id with authenticated user (prevent impersonation)
    try:
        result = await service.reject_discrepancy(
            discrepancy_id=discrepancy_id,
            level=rejection.level,
            rejecter_id=UUID(tenant_context.user_id),
            comments=rejection.comments,
        )
        return DiscrepancyResponse(
            id=result.id,
            observation_id=result.observation_id,
            category_id=result.category_id,
            school_id=result.school_id,
            department_id=result.department_id,
            raised_by_user_id=result.raised_by_user_id,
            investigation_owner_id=result.investigation_owner_id,
            state=result.state,
            investigation_findings=result.investigation_findings,
            bound_chain_version_id=result.bound_chain_version_id,
            raised_at=result.raised_at.isoformat() if result.raised_at else None,
            under_investigation_at=result.under_investigation_at.isoformat() if result.under_investigation_at else None,
            resolved_at=result.resolved_at.isoformat() if result.resolved_at else None,
            closed_at=result.closed_at.isoformat() if result.closed_at else None,
            created_at=result.created_at.isoformat() if result.created_at else None,
            updated_at=result.updated_at.isoformat() if result.updated_at else None,
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/discrepancies/{discrepancy_id}/approval-history", response_model=List[DiscrepancyApprovalHistoryResponse])
async def get_approval_history(
    discrepancy_id: UUID,
    tenant_context = Depends(require_tenant_context),
    service: DiscrepancyService = Depends(get_discrepancy_service),
):
    """
    Get approval history for a discrepancy.
    Returns one row per approval level with correct Role/User/Status/Comments (not fixed columns).
    """
    try:
        history = await service.get_approval_history(discrepancy_id=discrepancy_id)
        return [
            DiscrepancyApprovalHistoryResponse(
                id=entry.id,
                discrepancy_id=entry.discrepancy_id,
                level=entry.level,
                assigned_role_id=entry.assigned_role_id,
                approved_by_user_id=entry.approved_by_user_id,
                status=entry.status,
                comments=entry.comments,
                approved_at=entry.approved_at.isoformat() if entry.approved_at else None,
                created_at=entry.created_at.isoformat() if entry.created_at else None,
            )
            for entry in history
        ]
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
