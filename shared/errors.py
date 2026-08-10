"""
Shared error contract per API-Spec §3 and coding-standards.md §3.
Defines structured error responses and exception classes.
"""
from typing import Optional, Any, Dict
from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """
    Standard error response envelope per API-Spec §3.
    """
    error: "ErrorDetail"


class ErrorDetail(BaseModel):
    """
    Error detail structure.
    """
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class APIError(HTTPException):
    """
    Base API error class with structured error response.
    """
    
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.field = field
        self.details = details
        
        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "field": field,
                    "details": details
                }
            }
        )


class ValidationError(APIError):
    """
    Validation error (400) - structured, field-referenced.
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=message,
            field=field,
            details=details
        )


class AuthenticationError(APIError):
    """
    Authentication error (401) - missing/expired auth token.
    """
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_ERROR",
            message=message
        )


class AuthorizationError(APIError):
    """
    Authorization error (403) - authenticated but not permitted.
    """
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="AUTHORIZATION_ERROR",
            message=message
        )


class NotFoundError(APIError):
    """
    Not found error (404) - resource not found or not visible within scope.
    Intentionally indistinguishable cross-tenant to avoid leaking existence.
    """
    
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"{resource} not found"
        )


class ConflictError(APIError):
    """
    Conflict error (409) - duplicate name, concurrent audit action, immutability violation.
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            message=message,
            details=details
        )


class BusinessRuleError(APIError):
    """
    Business rule violation (422) - well-formed request that violates a business rule.
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="BUSINESS_RULE_VIOLATION",
            message=message,
            details=details
        )


class InternalServerError(APIError):
    """
    Internal server error (500) - unhandled server error.
    Always logged to Audit Log per API-Spec §3.
    """
    
    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message=message
        )


class PaginationResponse(BaseModel):
    """
    Pagination metadata per API-Spec §4.
    """
    page: int
    page_size: int
    total_count: int
    has_next: bool


class ListResponse(BaseModel):
    """
    Standard list endpoint response envelope per API-Spec §4.
    """
    data: list
    pagination: PaginationResponse
