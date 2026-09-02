"""
Custom exception handlers for org management API.
Returns consistent JSON error responses.
"""
from fastapi import Request
from fastapi.responses import JSONResponse

from shared.errors import NotFoundError, ValidationError, AuthorizationError, BusinessRuleError


async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "NOT_FOUND", "message": str(exc)}},
    )


async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "field": getattr(exc, "field", None),
            }
        },
    )


async def authorization_error_handler(request: Request, exc: AuthorizationError):
    return JSONResponse(
        status_code=403,
        content={"error": {"code": "FORBIDDEN", "message": str(exc)}},
    )


async def business_rule_error_handler(request: Request, exc: BusinessRuleError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "BUSINESS_RULE_ERROR", "message": str(exc)}},
    )
