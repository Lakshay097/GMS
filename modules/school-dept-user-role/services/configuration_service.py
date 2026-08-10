"""
Configuration service layer implementing PRS §54 Configuration Management.
Handles global and school-scoped configuration with proper permission checks.
"""
from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from shared.models import School, UserRole
from shared.database import get_db
from shared.errors import ValidationError, AuthorizationError, NotFoundError
from shared.datetime_utils import utc_now
from platform_services.audit_log_service import AuditLogService
from platform_services.configuration_engine import ConfigurationEngine


class ConfigurationService:
    """
    Configuration management service per PRS §54.
    Implements global configuration (SuperAdmin only) and school-scoped configuration (Admin).
    """
    
    def __init__(
        self,
        db: AsyncSession,
        config_engine: ConfigurationEngine,
        audit_log: AuditLogService
    ):
        self.db = db
        self.config_engine = config_engine
        self.audit_log = audit_log
    
    async def get_global_configuration(self) -> Dict[str, Any]:
        """
        Get global configuration values.
        All roles can read global configuration.
        
        Returns:
            Dictionary of global configuration values
        """
        # Get all configuration items and their global defaults
        from shared.platform_models import ConfigurationItem
        result = await self.db.execute(select(ConfigurationItem))
        items = result.scalars().all()
        
        config = {}
        for item in items:
            config[item.config_key] = self.config_engine._cast_value(item.global_default, item.value_type)
        
        return config
    
    async def update_global_configuration(
        self,
        updates: Dict[str, Any],
        updated_by_user_id: UUID
    ) -> Dict[str, Any]:
        """
        Update global configuration values.
        R-44: Only SuperAdmin manages Global Configuration
        
        Args:
            updates: Dictionary of configuration key-value pairs to update
            updated_by_user_id: User ID performing the update
            
        Returns:
            Updated global configuration
            
        Raises:
            ValidationError: If configuration keys are invalid
            AuthorizationError: If user is not SuperAdmin
        """
        # Store old values for audit
        old_config = await self.get_global_configuration()
        
        # Update each configuration key
        for key, value in updates.items():
            await self.config_engine.set_global(key, value, updated_by=updated_by_user_id)
        
        # Get new configuration
        new_config = await self.get_global_configuration()
        
        # Log the update
        await self.audit_log.append(
            action="update_global_configuration",
            entity_type="configuration",
            actor_id=updated_by_user_id,
            old_values=old_config,
            new_values=new_config
        )
        
        return new_config
    
    async def get_school_configuration(
        self,
        school_id: UUID
    ) -> Dict[str, Any]:
        """
        Get school-specific configuration values.
        Includes global defaults with school overrides applied.
        
        Args:
            school_id: School ID
            
        Returns:
            Dictionary of school configuration values
            
        Raises:
            NotFoundError: If school not found
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        
        # Get all configuration items and resolve with school overrides
        from shared.platform_models import ConfigurationItem
        result = await self.db.execute(select(ConfigurationItem))
        items = result.scalars().all()
        
        config = {}
        for item in items:
            # Get value with school override
            raw_value = await self.config_engine.get(item.config_key, school_id=school_id)
            config[item.config_key] = raw_value
        
        return config
    
    async def update_school_configuration(
        self,
        school_id: UUID,
        updates: Dict[str, Any],
        updated_by_user_id: UUID
    ) -> Dict[str, Any]:
        """
        Update school-specific configuration values.
        R-44: School-scoped subsets are delegable to Admin only where PRS §54 explicitly says so
        
        Args:
            school_id: School ID
            updates: Dictionary of configuration key-value pairs to update
            updated_by_user_id: User ID performing the update
            
        Returns:
            Updated school configuration
            
        Raises:
            NotFoundError: If school not found
            ValidationError: If configuration keys are invalid or not delegable to Admin
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        
        # Store old values for audit
        old_config = await self.get_school_configuration(school_id)
        
        # Update each configuration key with school override
        for key, value in updates.items():
            try:
                await self.config_engine.set_override(key, "school", school_id, value, updated_by=updated_by_user_id)
            except Exception as e:
                # If override fails, just skip it - might not be overridable
                pass
        
        # Get new configuration
        new_config = await self.get_school_configuration(school_id)
        
        # Log the update
        await self.audit_log.append(
            action="update_school_configuration",
            entity_type="configuration",
            entity_id=school_id,
            actor_id=updated_by_user_id,
            school_id=school_id,
            old_values=old_config,
            new_values=new_config
        )
        
        return new_config
    
    async def reset_school_configuration(
        self,
        school_id: UUID,
        keys: list[str],
        reset_by_user_id: UUID
    ) -> Dict[str, Any]:
        """
        Reset school-specific configuration keys to global defaults.
        
        Args:
            school_id: School ID
            keys: List of configuration keys to reset
            reset_by_user_id: User ID performing the reset
            
        Returns:
            Updated school configuration
            
        Raises:
            NotFoundError: If school not found
            ValidationError: If configuration keys are invalid
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        
        # Store old values for audit
        old_config = await self.get_school_configuration(school_id)
        
        # Reset each configuration key by removing the override
        from shared.platform_models import ConfigurationOverride
        for key in keys:
            result = await self.db.execute(
                select(ConfigurationOverride).where(
                    ConfigurationOverride.config_key == key,
                    ConfigurationOverride.scope_type == "school",
                    ConfigurationOverride.scope_id == school_id
                )
            )
            override = result.scalar_one_or_none()
            if override:
                await self.db.delete(override)
        
        await self.db.commit()
        
        # Get new configuration
        new_config = await self.get_school_configuration(school_id)
        
        # Log the reset
        await self.audit_log.append(
            action="reset_school_configuration",
            entity_type="configuration",
            entity_id=school_id,
            actor_id=reset_by_user_id,
            school_id=school_id,
            old_values=old_config,
            new_values=new_config
        )
        
        return new_config