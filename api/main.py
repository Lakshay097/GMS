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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

# API metadata per API-Spec
API_TITLE = "School Operations & Governance Platform API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "API for School Operations & Governance Platform"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print(f"Starting {API_TITLE} v{API_VERSION}")
    try:
        from modules.dashboards_reports_search.services.search_indexer import SearchIndexer
        await SearchIndexer.ensure_indexes()
        print("Search indexes bootstrapped")
    except Exception as e:
        print(f"Warning: Search index bootstrap failed (Meilisearch may be offline): {e}")
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

# CORS middleware with HTTPS support (data in transit per R-57)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler per API-Spec §3
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to ensure all errors follow the error contract.
    500 errors are logged to Audit Log per API-Spec §3.
    """
    from shared.errors import InternalServerError
    
    # Log to console (in production, this would log to Audit Log)
    print(f"Unhandled exception: {exc}")
    
    # Return structured error response
    error_response = InternalServerError(str(exc))
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


# Import and include routers
from api.auth import router as auth_router

# Placeholder for v1 router
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include auth router
v1_router.include_router(auth_router)

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
    
    # Include module routers
    v1_router.include_router(schools_router)
    v1_router.include_router(departments_router)
    v1_router.include_router(users_router)
    v1_router.include_router(configuration_router)
    v1_router.include_router(personal_settings_router)
except ImportError as e:
    print(f"Warning: Could not import module routers: {e}")
    print("Module routers will be available when dependencies are installed.")

# Settings & Master Data module (v1.5)
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "modules" / "settings-master-data"))
    from api.routes import router as settings_master_data_router
    from api.configuration_routes import router as settings_configuration_router
    v1_router.include_router(settings_master_data_router)
    v1_router.include_router(settings_configuration_router)
except Exception as e:
    print(f"Warning: Could not import settings-master-data router: {e}")

# Audit Discrepancy module (v1.5)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "modules" / "audit-discrepancy"))
    from api.routes import router as audit_discrepancy_router
    v1_router.include_router(audit_discrepancy_router)
except Exception as e:
    print(f"Warning: Could not import audit-discrepancy router: {e}")

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

# Observation Capture Evidence Routes (v1.5) — PRS §47/BR-27
try:
    from modules.observation_capture.api.evidence_routes import router as evidence_router
    v1_router.include_router(evidence_router)
except Exception as e:
    print(f"Warning: Could not import observation-capture evidence router: {e}")

# Include v1 router
app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )