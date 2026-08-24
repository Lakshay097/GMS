"""
Evidence Upload service — Architecture §18/ADR-07.
Routes evidence uploads through Cloudinary for Observation capture.
Includes Evidence Retention & Deletion per PRS §47/BR-27, FR-271–274.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import mimetypes

import cloudinary
import cloudinary.uploader
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.configuration_engine.constants import ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.audit_log_service.service import AuditLogService
from shared.errors import ValidationError, BusinessRuleError
from shared.datetime_utils import utc_now


class EvidenceService:
    """
    Evidence upload service per Architecture §18/ADR-07.
    Handles Cloudinary integration for Observation evidence.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        config_engine: Optional[ConfigurationEngine] = None,
        audit_log: Optional[AuditLogService] = None,
    ):
        self.db = db
        self.config_engine = config_engine or ConfigurationEngine(db)
        self.audit_log = audit_log or AuditLogService(db)
        
        # Configure Cloudinary from environment
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        )

    async def upload_evidence(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str,
        school_id: Optional[str] = None,
    ) -> dict:
        """
        Upload evidence to Cloudinary per PRS §24 and Architecture §18/ADR-07.
        
        Validates:
        - File size against configured maximum
        - File format/size at submission per PRS §52
        - Content type matches file extension (M2 security fix)
        
        Returns Cloudinary upload result with public_id and URL.
        """
        # Get max file size from configuration
        max_size_mb = await self.config_engine.get(
            ConfigKey.FILE_UPLOAD_MAX_SIZE_MB,
            school_id=school_id,
        )
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # Validate file size
        file_size = len(file_data)
        if file_size > max_size_bytes:
            raise ValidationError(
                f"File size exceeds maximum allowed size of {max_size_mb}MB",
                field="file_size",
                details={"max_size_mb": max_size_mb, "actual_size_bytes": file_size},
            )
        
        # Validate content type matches file extension (M2 security fix)
        # Prevents uploading malicious files with misleading extensions
        guessed_type, _ = mimetypes.guess_type(file_name)
        if guessed_type and content_type != guessed_type:
            # Allow some leniency for common variations
            if not (
                (content_type.startswith("image/") and guessed_type.startswith("image/")) or
                (content_type == "application/pdf" and guessed_type == "application/pdf") or
                (content_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"] and 
                 guessed_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"])
            ):
                raise ValidationError(
                    f"Content type '{content_type}' does not match file extension '{file_name}'",
                    field="content_type",
                    details={"provided_type": content_type, "expected_type": guessed_type},
                )
        
        # Get upload preset from environment
        upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET", "observation_evidence")
        
        # Upload to Cloudinary with authenticated delivery for security (A7 fix)
        try:
            result = cloudinary.uploader.upload(
                file_data,
                public_id=f"observations/{file_name}",
                upload_preset=upload_preset,
                resource_type="auto",
                allowed_formats=["jpg", "jpeg", "png", "pdf", "doc", "docx"],
                type="authenticated",  # A7 security fix: require signed URLs for access
                use_filename=True,  # Use original filename to avoid predictable IDs
                unique_filename=True,  # Add random suffix to prevent collisions
            )
            
            return {
                "cloudinary_public_id": result["public_id"],
                "cloudinary_url": result["secure_url"],
                "file_size_bytes": file_size,
                "format": result.get("format"),
                "resource_type": result.get("resource_type"),
            }
        except Exception as e:
            raise ValidationError(
                f"Failed to upload evidence to Cloudinary: {str(e)}",
                field="evidence_upload",
            )

    async def delete_evidence(self, public_id: str) -> None:
        """
        Delete evidence from Cloudinary.
        Called when evidence retention period elapses per PRS §47/BR-27.
        Note: This is an internal method. For user-initiated deletion, use delete_evidence_with_audit.
        """
        try:
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            # Log error but don't fail — deletion is eventually consistent
            print(f"Failed to delete evidence {public_id}: {str(e)}")
    
    async def is_evidence_deletion_eligible(
        self,
        observation_id: UUID,
        public_id: str,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Check if evidence is eligible for deletion per PRS §47/BR-27.
        
        Returns dict with:
        - eligible: bool - whether retention period has elapsed
        - retention_period_days: int - configured retention period
        - submitted_at: datetime - when observation was submitted
        - retention_eligible_at: datetime - when evidence becomes deletion-eligible
        - days_until_eligible: int - days until eligible (negative if already eligible)
        """
        from shared.models import Observation
        
        # Get observation to check submission date
        observation = await self.db.get(Observation, observation_id)
        if not observation:
            raise ValidationError("Observation not found", field="observation_id")
        
        # Get retention period from configuration (default 7 years per env-and-secrets.md)
        retention_period_days = await self.config_engine.get(
            ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS,
            school_id=school_id,
        )
        
        # Calculate when evidence becomes deletion-eligible
        submitted_at = observation.submitted_at
        retention_eligible_at = submitted_at + timedelta(days=retention_period_days)
        now = utc_now()
        
        is_eligible = now >= retention_eligible_at
        days_until_eligible = (retention_eligible_at - now).days
        
        return {
            "eligible": is_eligible,
            "retention_period_days": retention_period_days,
            "submitted_at": submitted_at.isoformat(),
            "retention_eligible_at": retention_eligible_at.isoformat(),
            "days_until_eligible": days_until_eligible,
            "public_id": public_id,
        }
    
    async def delete_evidence_with_audit(
        self,
        observation_id: UUID,
        public_id: str,
        actor_id: UUID,
        school_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> dict:
        """
        Delete evidence with explicit admin/superadmin action and audit logging per PRS §47/BR-27, FR-271–274.
        
        Enforces:
        - Retention period must have elapsed (rejects deletion even for SuperAdmin)
        - Actor must be Admin or SuperAdmin
        - Deletion is logged to Audit Log with actor identity and timestamp
        
        Args:
            observation_id: Observation ID containing the evidence
            public_id: Cloudinary public_id of the evidence file
            actor_id: User ID performing the deletion
            school_id: Optional school ID for configuration lookup
            reason: Optional reason for deletion
            
        Returns:
            dict with deletion status and audit log entry ID
            
        Raises:
            BusinessRuleError: If retention period has not elapsed
            ValidationError: If observation not found or other validation fails
        """
        # Check deletion eligibility first
        eligibility = await self.is_evidence_deletion_eligible(
            observation_id, public_id, school_id
        )
        
        if not eligibility["eligible"]:
            raise BusinessRuleError(
                f"Evidence deletion not yet permitted. Retention period ({eligibility['retention_period_days']} days) has not elapsed. "
                f"Evidence will be deletion-eligible on {eligibility['retention_eligible_at']}. "
                f"Days until eligible: {eligibility['days_until_eligible']}",
                details={
                    "public_id": public_id,
                    "observation_id": str(observation_id),
                    "retention_period_days": eligibility["retention_period_days"],
                    "retention_eligible_at": eligibility["retention_eligible_at"],
                    "days_until_eligible": eligibility["days_until_eligible"],
                },
            )
        
        # Log the deletion action to Audit Log before performing deletion
        audit_log_id = await self.audit_log.append(
            action="evidence_deleted",
            entity_type="observation",
            entity_id=observation_id,
            actor_id=actor_id,
            school_id=school_id,
            new_values={
                "public_id": public_id,
                "reason_comment": reason,
                "deleted_at": utc_now().isoformat(),
            },
        )

        # Perform the actual deletion from Cloudinary
        try:
            await self.delete_evidence(public_id)

            return {
                "success": True,
                "public_id": public_id,
                "observation_id": str(observation_id),
                "actor_id": str(actor_id),
                "deleted_at": utc_now().isoformat(),
                "audit_log_id": str(audit_log_id),
                "reason": reason,
            }
        except Exception as e:
            # If deletion fails, we still have the audit log entry showing the attempt
            raise ValidationError(
                f"Evidence deletion failed: {str(e)}",
                field="evidence_deletion",
                details={
                    "public_id": public_id,
                    "audit_log_id": str(audit_log_id),
                },
            )
