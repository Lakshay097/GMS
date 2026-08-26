"""
Main FastAPI application entry point.
REST API skeleton at /v1/ per API-Spec §1.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
import sentry_sdk
from shared.utils import get_client_ip
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
import os
import time
import traceback
from dotenv import load_dotenv
import sys
import logging

load_dotenv()

# Configure Sentry for error monitoring and performance tracking
sentry_dsn = os.getenv("SENTRY_BACKEND_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        # Add data like request headers and IP for users
        send_default_pii=True,
        # Enable sending logs to Sentry
        enable_logs=True,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for tracing.
        traces_sample_rate=1.0,
        # Set profile_session_sample_rate to 1.0 to profile 100%
        # of profile sessions.
        profile_session_sample_rate=1.0,
        # Set profile_lifecycle to "trace" to automatically
        # run the profiler on when there is an active transaction
        profile_lifecycle="trace",
    )
    print("Sentry initialized for backend")
else:
    print("Sentry backend DSN not configured - skipping Sentry initialization")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API metadata per API-Spec
API_TITLE = "SchoolOps API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "API for SchoolOps"


def validate_startup_config():
    """
    Validate required environment variables on startup.
    Fails fast with clear error messages if critical configuration is missing.
    """
    env = os.getenv("ENV", "development")
    
    # Required for all environments
    required_vars = ["DATABASE_URL"]
    
    # Required for production
    if env == "production":
        required_vars.extend([
            "ENCRYPTION_KEY",
            "INTERNAL_SCHEDULER_SECRET",
            "CORS_ORIGINS"
        ])
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"CRITICAL: Missing required environment variables: {', '.join(missing_vars)}")
        print(f"Environment: {env}")
        print("Please set these variables and restart the application.")
        sys.exit(1)
    
    # Validate ENCRYPTION_KEY is not default in production
    if env == "production":
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key or len(encryption_key) < 32:
            print("CRITICAL: ENCRYPTION_KEY must be at least 32 characters in production")
            sys.exit(1)
        
        # Validate INTERNAL_SCHEDULER_SECRET is not a known default
        scheduler_secret = os.getenv("INTERNAL_SCHEDULER_SECRET")
        default_secrets = ["secret", "password", "changeme", "default", "test"]
        if scheduler_secret.lower() in default_secrets:
            print("CRITICAL: INTERNAL_SCHEDULER_SECRET must not use default values in production")
            sys.exit(1)
        
        # Validate CORS_ORIGINS is not wildcard when credentials are enabled
        cors_origins = os.getenv("CORS_ORIGINS", "")
        if cors_origins:
            origins_list = [origin.strip() for origin in cors_origins.split(",")]
            if "*" in origins_list:
                print("CRITICAL: CORS_ORIGINS contains '*' in production with allow_credentials=True")
                print("This is a security risk. Browsers will reject cookie-based auth with wildcard origins.")
                print("Please set explicit origins in CORS_ORIGINS environment variable.")
                sys.exit(1)
        else:
            print("WARNING: CORS_ORIGINS not set in production. This will cause failures with cookie-based auth.")
            print("Please set explicit origins in CORS_ORIGINS environment variable.")
    
    print(f"Configuration validation passed for environment: {env}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print(f"Starting {API_TITLE} v{API_VERSION}")
    
    # Validate required environment variables
    validate_startup_config()
    
    # Temporarily disable search indexer to speed up startup
    print("Skipping search index bootstrap (temporarily disabled)")
    
    # Initialize permissions matrix
    # Temporarily disabled to troubleshoot startup issues
    print("Skipping permissions initialization for debugging")
    
    print("Application startup complete")
    yield
    # Shutdown
    print(f"Shutting down {API_TITLE}")
    try:
        from shared.database import close_db
        await close_db()
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Rate limiting configuration for security (H3)
limiter = Limiter(key_func=get_client_ip)
app.state.limiter = limiter

# Add rate limiting exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with HTTPS support (data in transit per R-57)
# In production, require explicit origins. In development, allow localhost for convenience.
env = os.getenv("ENV", "development")
cors_origins = os.getenv("CORS_ORIGINS", "*")

if env == "production":
    if cors_origins == "*":
        print("WARNING: CORS_ORIGINS is '*' in production. This is insecure with allow_credentials=True.")
        print("Please set explicit origins in CORS_ORIGINS environment variable.")
    # In production, we accept the configured value but warn if it's wildcard
else:
    # In development, default to localhost for convenience
    # Include port 5173 (Vite dev server default) alongside legacy 3000/8000
    if cors_origins == "*":
        cors_origins = (
            "http://localhost:3000,http://localhost:5173,http://localhost:8000,"
            "http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8000"
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip middleware for response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security headers middleware (L2 security fix)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses (L2 security fix)."""
    response = await call_next(request)
    
    env = os.getenv("ENV", "development")
    
    # Content Security Policy (L2)
    # In development, allow inline scripts for easier debugging
    if env == "production":
        csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none';"
    else:
        csp = "default-src 'self' 'unsafe-inline' 'unsafe-eval'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https: http:; font-src 'self'; connect-src 'self' ws: wss:;"
    
    response.headers["Content-Security-Policy"] = csp
    
    # Prevent clickjacking (L2)
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME type sniffing (L2)
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Referrer policy (L2)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # HSTS in production (L2)
    if env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # XSS Protection (legacy but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    return response

# Performance timing middleware
@app.middleware("http")
async def add_performance_timing(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log request metrics for basic APM (L3 security fix)
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    return response


# Global exception handler per API-Spec §3
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to ensure all errors follow the error contract.
    500 errors are logged to Audit Log per API-Spec §3.
    
    L1 Security Fix: Sanitize errors in production to prevent information leakage.
    """
    from shared.errors import InternalServerError
    
    env = os.getenv("ENV", "development")
    
    # Log full error details for debugging (L1 security fix)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # In production, return generic error message (L1 security fix)
    if env == "production":
        error_message = "An internal server error occurred. Please try again later."
    else:
        # In development, return actual error for debugging
        error_message = str(exc)
    
    # Return structured error response
    error_response = InternalServerError(error_message)
    return JSONResponse(
        status_code=500,
        content=error_response.detail
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {
        "status": "healthy",
        "version": API_VERSION,
        "service": "school-operations-platform"
    }


# Sentry debug endpoint for verification
@app.get("/sentry-debug")
async def trigger_error():
    """
    Sentry debug endpoint to trigger an error for verification.
    """
    division_by_zero = 1 / 0


# Import and include routers
from api.auth import router as auth_router
from api.webhooks import router as webhooks_router
from api.internal_routes import router as internal_router

# Include internal scheduler routes (for Cloud Scheduler)
app.include_router(internal_router)

# Include webhooks router (Clerk webhooks)
app.include_router(webhooks_router)

# Placeholder for v1 router
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include auth router
app.include_router(auth_router)  # Include auth router at root level, not in v1

# KRA/KPI Library module (PRS §22-23)
try:
    from modules.kra_kpi_library.api.routes import router as kra_kpi_router
    v1_router.include_router(kra_kpi_router)
except ImportError as e:
    print(f"Warning: Could not import KRA/KPI router: {e}")

# Try to include module routers
try:
    from modules.school_dept_user_role.api.schools import router as schools_router
    from modules.school_dept_user_role.api.departments import router as departments_router
    from modules.school_dept_user_role.api.users import router as users_router
    from modules.school_dept_user_role.api.configuration import router as configuration_router
    from modules.school_dept_user_role.api.personal_settings import router as personal_settings_router
    from modules.school_dept_user_role.api.approvals import router as approvals_router
    
    # Include module routers
    v1_router.include_router(schools_router)
    v1_router.include_router(departments_router)
    v1_router.include_router(users_router)
    v1_router.include_router(configuration_router)
    v1_router.include_router(personal_settings_router)
    v1_router.include_router(approvals_router)
except ImportError as e:
    print(f"Warning: Could not import module routers: {e}")
    print("Module routers will be available when dependencies are installed.")

# Settings & Master Data module (v1.5)
try:
    from modules.settings_master_data.api.routes import router as settings_master_data_router
    from modules.settings_master_data.api.configuration_routes import router as settings_configuration_router
    v1_router.include_router(settings_master_data_router)
    v1_router.include_router(settings_configuration_router)
except Exception as e:
    print(f"Warning: Could not import settings_master_data router: {e}")

# Audit Discrepancy module (v1.5)
try:
    from modules.audit_discrepancy.api.routes import router as audit_discrepancy_router
    v1_router.include_router(audit_discrepancy_router)
except Exception as e:
    print(f"Warning: Could not import audit_discrepancy router: {e}")

# Task Management module — PRS §27
try:
    from modules.task_management.api.routes import router as task_router
    from modules.task_management.api.routes import escalation_rules_router
    v1_router.include_router(task_router)
    v1_router.include_router(escalation_rules_router)
except Exception as e:
    print(f"Warning: Could not import task-management router: {e}")

# Dashboards, Report Catalogue, Global Search — PRS §30-31, §33, §50
try:
    from modules.dashboards_reports_search.api.routes import router as dash_router
    v1_router.include_router(dash_router)
except Exception as e:
    print(f"Warning: Could not import dashboards-reports-search router: {e}")

# Observation Capture Routes — PRS §24
try:
    from modules.observation_capture.api.routes import router as observation_router
    v1_router.include_router(observation_router)
except Exception as e:
    print(f"Warning: Could not import observation-capture router: {e}")

# Observation Capture Evidence Routes (v1.5) — PRS §47/BR-27
# Re-enabled with security fixes (M2)
try:
    from modules.observation_capture.api.evidence_routes import router as evidence_router
    v1_router.include_router(evidence_router)
except Exception as e:
    print(f"Warning: Could not import observation-capture evidence router: {e}")

# Include v1 router
app.include_router(v1_router)

# ── Static frontend serving (Cloud Run) ──────────────────────────────────────
# Serve the Vite-built frontend from frontend/dist so the same container
# handles both the API and the SPA.  API routes above take priority.
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    # Serve hashed assets (JS, CSS, images) with long cache
    _assets = _frontend_dist / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="static-assets")

    # Serve other static files (favicon, robots.txt, etc.)
    app.mount("/static", StaticFiles(directory=_frontend_dist), name="static-root")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all: serve index.html for client-side routing."""
        # If a specific file exists, serve it (favicon, manifest, etc.)
        file_path = _frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for React Router
        return FileResponse(_frontend_dist / "index.html")
else:
    print(f"WARNING: Frontend dist not found at {_frontend_dist}. SPA serving disabled.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )