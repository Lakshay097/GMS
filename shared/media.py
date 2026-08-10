"""
Cloudinary integration for media and evidence storage per ADR-07.
Handles file uploads, deletions, and URL generation.
"""
import os
from typing import Optional, Dict, Any
from cloudinary import CloudinaryImage, uploader
from cloudinary.api import delete_resources
from dotenv import load_dotenv

load_dotenv()

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
CLOUDINARY_UPLOAD_PRESET = os.getenv("CLOUDINARY_UPLOAD_PRESET")
FILE_UPLOAD_MAX_SIZE_MB = int(os.getenv("FILE_UPLOAD_MAX_SIZE_MB", "10"))
EVIDENCE_RETENTION_PERIOD_DAYS = int(os.getenv("EVIDENCE_RETENTION_PERIOD_DAYS", "90"))

# Configure Cloudinary
if CLOUDINARY_CLOUD_NAME:
    import cloudinary
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )


class MediaStorageService:
    """
    Service for managing media storage via Cloudinary.
    """
    
    def __init__(self):
        self.cloud_name = CLOUDINARY_CLOUD_NAME
        self.upload_preset = CLOUDINARY_UPLOAD_PRESET
        self.max_size_bytes = FILE_UPLOAD_MAX_SIZE_MB * 1024 * 1024
        self.retention_days = EVIDENCE_RETENTION_PERIOD_DAYS
    
    async def upload_file(
        self,
        file_path: str,
        resource_type: str = "auto",
        folder: Optional[str] = None,
        public_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to Cloudinary.
        
        Args:
            file_path: Path to the file to upload
            resource_type: Type of resource (image, video, raw, auto)
            folder: Cloudinary folder for organization
            public_id: Optional custom public ID
            
        Returns:
            Upload response with URL and metadata
        """
        upload_options = {
            "resource_type": resource_type,
            "upload_preset": self.upload_preset,
        }
        
        if folder:
            upload_options["folder"] = folder
        
        if public_id:
            upload_options["public_id"] = public_id
        
        result = uploader.upload(file_path, **upload_options)
        
        return {
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "resource_type": result["resource_type"],
            "bytes": result["bytes"],
            "format": result["format"],
            "created_at": result["created_at"]
        }
    
    async def upload_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        resource_type: str = "auto",
        folder: Optional[str] = None,
        public_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload file bytes to Cloudinary.
        
        Args:
            file_bytes: File content as bytes
            filename: Original filename
            resource_type: Type of resource (image, video, raw, auto)
            folder: Cloudinary folder for organization
            public_id: Optional custom public ID
            
        Returns:
            Upload response with URL and metadata
        """
        upload_options = {
            "resource_type": resource_type,
            "upload_preset": self.upload_preset,
        }
        
        if folder:
            upload_options["folder"] = folder
        
        if public_id:
            upload_options["public_id"] = public_id
        
        result = uploader.upload(
            file_bytes,
            filename=filename,
            **upload_options
        )
        
        return {
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "resource_type": result["resource_type"],
            "bytes": result["bytes"],
            "format": result["format"],
            "created_at": result["created_at"]
        }
    
    async def delete_file(self, public_id: str, resource_type: str = "image") -> bool:
        """
        Delete a file from Cloudinary.
        
        Args:
            public_id: Public ID of the resource to delete
            resource_type: Type of resource
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = uploader.destroy(public_id, resource_type=resource_type)
            return result.get("result") == "ok"
        except Exception:
            return False
    
    async def delete_multiple(self, public_ids: list, resource_type: str = "image") -> Dict[str, Any]:
        """
        Delete multiple files from Cloudinary.
        
        Args:
            public_ids: List of public IDs to delete
            resource_type: Type of resource
            
        Returns:
            Deletion result
        """
        return delete_resources(public_ids, resource_type=resource_type)
    
    async def get_file_info(self, public_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file.
        
        Args:
            public_id: Public ID of the resource
            
        Returns:
            File metadata if found, None otherwise
        """
        try:
            result = uploader.resource(public_id)
            return {
                "public_id": result["public_id"],
                "url": result["secure_url"],
                "bytes": result["bytes"],
                "format": result["format"],
                "created_at": result["created_at"]
            }
        except Exception:
            return None
    
    def generate_url(
        self,
        public_id: str,
        transformations: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a URL for a Cloudinary resource with optional transformations.
        
        Args:
            public_id: Public ID of the resource
            transformations: Optional transformation parameters
            
        Returns:
            Secure URL for the resource
        """
        image = CloudinaryImage(public_id)
        if transformations:
            return image.build_url(**transformations)
        return image.build_url()
    
    def validate_file_size(self, file_size: int) -> bool:
        """
        Validate file size against maximum allowed size.
        
        Args:
            file_size: File size in bytes
            
        Returns:
            True if size is valid, False otherwise
        """
        return file_size <= self.max_size_bytes


# Global media storage service instance
media_storage = MediaStorageService()
