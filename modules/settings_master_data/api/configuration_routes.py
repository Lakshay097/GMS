"""
Settings API routes per PRS §34 Configuration Management.
Exposes Configuration Engine items to SuperAdmin (all items) and Admin (school-scoped subset).
Uses permission middleware from Prompt 3.
"""
from typing import Optional, List, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.errors import ValidationError as ServiceValidationError
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey, CONFIG_DEFINITIONS
from shared.middleware import get_current_user

router = APIRouter(prefix="/settings/configuration", tags=["settings-configuration"])


# ── Schemas ──────────────────────────────────────────────────────────────

class ConfigurationItemResponse(BaseModel):
    config_key: str
    value_type: str
    global_default: str
    editable_by: str
    overridable_scope: str
    current_value: Optional[str] = None
    school_override: Optional[str] = None


class ConfigurationUpdateRequest(BaseModel):
    value: str
    scope_type: Optional[str] = Field(None, description="global, school, or department")
    scope_id: Optional[UUID] = Field(None, description="School or Department ID for scope-specific overrides")


class ConfigurationBatchUpdateRequest(BaseModel):
    updates: List[dict] = Field(..., description="List of config_key -> value mappings")


# ── Configuration Endpoints ─────────────────────────────────────────────

@router.get("/", response_model=List[ConfigurationItemResponse])
async def list_configuration_items(
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    List all configuration items.
    SuperAdmin sees all items; Admin sees only items delegable to school scope per PRS §54.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Permission check via matrix: only SuperAdmin can manage global configuration
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    try:
        await PermissionChecker.require_permission(
            Module.GLOBAL_CONFIGURATION, Action.MANAGE, current_user, db
        )
        is_super_admin = True
    except Exception:
        is_super_admin = False
    
    items = []
    for config_key, definition in CONFIG_DEFINITIONS.items():
        # Filter for Admin: only show items that are school-scoped or global
        if not is_super_admin and definition["overridable_scope"] not in ("school", "none"):
            continue
        
        # Get current value for the requested scope
        try:
            current_value = await config_engine.get(
                config_key,
                school_id=school_id if definition["overridable_scope"] == "school" else None,
            )
            current_value_str = str(current_value) if current_value is not None else None
        except Exception:
            current_value_str = None
        
        # Get school override if applicable
        school_override = None
        if school_id and definition["overridable_scope"] == "school":
            try:
                override = await config_engine._get_override(config_key, "school", school_id)
                school_override = override
            except Exception:
                pass
        
        items.append(ConfigurationItemResponse(
            config_key=config_key,
            value_type=definition["value_type"],
            global_default=definition["global_default"],
            editable_by=definition["editable_by"],
            overridable_scope=definition["overridable_scope"],
            current_value=current_value_str,
            school_override=school_override,
        ))
    
    return items


@router.get("/{config_key}", response_model=ConfigurationItemResponse)
async def get_configuration_item(
    config_key: str,
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get a specific configuration item by key."""
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Check if item exists
    if config_key not in CONFIG_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration key not found")
    
    definition = CONFIG_DEFINITIONS[config_key]
    
    # Check permission: Admin can only access school-scoped items
    # Permission check via matrix: only SuperAdmin can manage global configuration
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    try:
        await PermissionChecker.require_permission(
            Module.GLOBAL_CONFIGURATION, Action.MANAGE, current_user, db
        )
        is_super_admin = True
    except Exception:
        is_super_admin = False
    if not is_super_admin and definition["overridable_scope"] not in ("school", "none"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Get current value
    try:
        current_value = await config_engine.get(
            config_key,
            school_id=school_id if definition["overridable_scope"] == "school" else None,
        )
        current_value_str = str(current_value) if current_value is not None else None
    except Exception:
        current_value_str = None
    
    # Get school override if applicable
    school_override = None
    if school_id and definition["overridable_scope"] == "school":
        try:
            override = await config_engine._get_override(config_key, "school", school_id)
            school_override = override
        except Exception:
            pass
    
    return ConfigurationItemResponse(
        config_key=config_key,
        value_type=definition["value_type"],
        global_default=definition["global_default"],
        editable_by=definition["editable_by"],
        overridable_scope=definition["overridable_scope"],
        current_value=current_value_str,
        school_override=school_override,
    )


@router.patch("/{config_key}", response_model=ConfigurationItemResponse)
async def update_configuration_item(
    config_key: str,
    request: ConfigurationUpdateRequest,
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update a configuration item.
    SuperAdmin can update global defaults; Admin can update school-scoped overrides per PRS §54.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Check if item exists
    if config_key not in CONFIG_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration key not found")
    
    definition = CONFIG_DEFINITIONS[config_key]
    # Permission check via matrix: only SuperAdmin can manage global configuration
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    try:
        await PermissionChecker.require_permission(
            Module.GLOBAL_CONFIGURATION, Action.MANAGE, current_user, db
        )
        is_super_admin = True
    except Exception:
        is_super_admin = False
    is_admin = "admin" in normalized_roles
    
    # Permission checks per PRS §54
    if request.scope_type == "global":
        if not is_super_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SuperAdmin can update global defaults")
        if definition["editable_by"] != "super_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This item is not editable by SuperAdmin")
        await config_engine.set_global(config_key, request.value, updated_by=current_user.user_id)
    
    elif request.scope_type == "school":
        if not (is_super_admin or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin or SuperAdmin can set school overrides")
        if definition["overridable_scope"] != "school":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This item does not support school overrides")
        if not request.scope_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope_id required for school overrides")
        await config_engine.set_override(config_key, "school", request.scope_id, request.value, updated_by=current_user.user_id)
    
    elif request.scope_type == "department":
        if not is_super_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SuperAdmin can set department overrides")
        if definition["overridable_scope"] != "department":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This item does not support department overrides")
        if not request.scope_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope_id required for department overrides")
        await config_engine.set_override(config_key, "department", request.scope_id, request.value, updated_by=current_user.user_id)
    
    else:
        # Default to global if no scope specified
        if not is_super_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SuperAdmin can update global defaults")
        await config_engine.set_global(config_key, request.value, updated_by=current_user.user_id)
    
    # Return updated item
    return await get_configuration_item(config_key, school_id, db, current_user)


@router.post("/batch-update", response_model=List[ConfigurationItemResponse])
async def batch_update_configuration(
    request: ConfigurationBatchUpdateRequest,
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Batch update multiple configuration items.
    Each update in the list must specify config_key, value, and optional scope_type/scope_id.
    """
    updated_items = []
    
    for update in request.updates:
        config_key = update.get("config_key")
        value = update.get("value")
        scope_type = update.get("scope_type")
        scope_id = update.get("scope_id")
        
        if not config_key or value is None:
            continue
        
        try:
            update_request = ConfigurationUpdateRequest(
                value=value,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            updated_item = await update_configuration_item(
                config_key, update_request, school_id, db, current_user
            )
            updated_items.append(updated_item)
        except HTTPException:
            # Skip items that fail validation/permission checks
            continue
    
    return updated_items


@router.delete("/{config_key}/overrides/{scope_type}/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_configuration_override(
    config_key: str,
    scope_type: str,
    scope_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Delete a configuration override (school or department level).
    Restores the global default for that scope.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Check if item exists
    if config_key not in CONFIG_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration key not found")
    
    definition = CONFIG_DEFINITIONS[config_key]
    # Permission check via matrix: only SuperAdmin can manage global configuration
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    try:
        await PermissionChecker.require_permission(
            Module.GLOBAL_CONFIGURATION, Action.MANAGE, current_user, db
        )
        is_super_admin = True
    except Exception:
        is_super_admin = False
    
    # Permission checks
    if scope_type == "school":
        if not is_super_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SuperAdmin can delete school overrides")
        if definition["overridable_scope"] != "school":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This item does not support school overrides")
    elif scope_type == "department":
        if not is_super_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SuperAdmin can delete department overrides")
        if definition["overridable_scope"] != "department":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This item does not support department overrides")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid scope_type")
    
    # Delete the override by setting it to None (effectively removes it)
    try:
        # Get the override record and delete it
        from shared.platform_models import ConfigurationOverride
        from sqlalchemy import select, delete
        
        result = await db.execute(
            delete(ConfigurationOverride).where(
                ConfigurationOverride.config_key == config_key,
                ConfigurationOverride.scope_type == scope_type,
                ConfigurationOverride.scope_id == scope_id,
            )
        )
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
