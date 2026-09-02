"""
Tests for FR-163: Language Preference selection.

Covers the user-facing API surface:
- GET  /api/v1/settings/me  — read own language_preference
- PATCH /api/v1/settings/me — update own language_preference (LOCALES-validated)
- PATCH /api/v1/users/{id}  — authorization: non-admin cannot set another user's preference

Uses real services, real TenantContext, and the real API-layer authorization checks
(ADR-09). Authorization logic is not mocked.
"""
import pytest
import sys
import os
from pathlib import Path
from uuid import uuid4

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ["QUEUE_PROVIDER"] = "memory"
from shared.task_queue import reset_queue_instance
reset_queue_instance()

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from shared.database import get_db
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.models import School, SchoolStatus, User, UserStatus, UserRole
from shared.task_queue import InMemoryQueue
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.audit_log_service import AuditLogService
from platform_services.notification_service.service import NotificationService
from modules.school_dept_user_role.services.user_service import UserService
from modules.school_dept_user_role.api import personal_settings as personal_settings_api
from modules.school_dept_user_role.api import users as users_api


def _tenant_for(user: User) -> TenantContext:
    """Build a real TenantContext for the given user (not a mock of auth checks)."""
    return TenantContext(
        user_id=str(user.id),
        school_id=str(user.school_id) if user.school_id else None,
        department_id=str(user.department_id) if user.department_id else None,
        roles=list(user.roles or []),
    )


def _user_service_factory(db: AsyncSession) -> UserService:
    """Real UserService with in-memory queue (avoids SQS/boto3 in tests)."""
    audit_log = AuditLogService(db)
    notification_service = NotificationService(db, queue=InMemoryQueue())
    return UserService(db, audit_log, notification_service=notification_service)


async def _create_school_and_users(db_session: AsyncSession):
    """Seed school + two checker users for preference tests."""
    school = School(
        name="Lang Pref School",
        code=f"LP{uuid4().hex[:6].upper()}",
        status=SchoolStatus.ACTIVE,
    )
    db_session.add(school)
    await db_session.flush()

    actor = User(
        clerk_user_id=f"clerk-actor-{uuid4().hex[:8]}",
        email=f"actor-{uuid4()}@example.com",
        full_name="Actor User",
        school_id=school.id,
        status=UserStatus.ACTIVE,
        roles=[UserRole.CHECKER.value],
        language_preference="en",
        mfa_enabled=False,
    )
    other = User(
        clerk_user_id=f"clerk-other-{uuid4().hex[:8]}",
        email=f"other-{uuid4()}@example.com",
        full_name="Other User",
        school_id=school.id,
        status=UserStatus.ACTIVE,
        roles=[UserRole.CHECKER.value],
        language_preference="en",
        mfa_enabled=False,
    )
    db_session.add_all([actor, other])
    await db_session.commit()
    await db_session.refresh(actor)
    await db_session.refresh(other)

    config_engine = ConfigurationEngine(db_session)
    await config_engine.seed_defaults()

    return school, actor, other


@pytest.fixture
async def api_client(db_session: AsyncSession):
    """
    FastAPI AsyncClient with the test DB and real UserService injected.
    Tenant context is overridden per-test via app.dependency_overrides.
    Authorization checks inside the route handlers are NOT mocked.
    """
    async def override_get_db():
        yield db_session

    def override_user_service():
        return _user_service_factory(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[personal_settings_api.get_user_service] = override_user_service
    app.dependency_overrides[users_api.get_user_service] = override_user_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_language_preference_read_success(db_session: AsyncSession, api_client: AsyncClient):
    """
    FR-163: Authenticated user can read their own language_preference via GET /settings/me.
    """
    _, actor, _ = await _create_school_and_users(db_session)
    app.dependency_overrides[require_tenant_context] = lambda: _tenant_for(actor)

    response = await api_client.get("/api/v1/settings/me")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["language_preference"] == "en"


@pytest.mark.asyncio
async def test_language_preference_update_valid_locale(db_session: AsyncSession, api_client: AsyncClient):
    """
    FR-163: Authenticated user can set language_preference to a valid LOCALES value.
    """
    _, actor, _ = await _create_school_and_users(db_session)
    app.dependency_overrides[require_tenant_context] = lambda: _tenant_for(actor)

    response = await api_client.patch(
        "/api/v1/settings/me",
        json={"language_preference": "hi"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["language_preference"] == "hi"

    # Persist check
    await db_session.refresh(actor)
    assert actor.language_preference == "hi"

    # Read-back via GET
    read_response = await api_client.get("/api/v1/settings/me")
    assert read_response.status_code == 200
    assert read_response.json()["language_preference"] == "hi"


@pytest.mark.asyncio
async def test_language_preference_reject_invalid_locale(db_session: AsyncSession, api_client: AsyncClient):
    """
    FR-163: Values outside ConfigurationEngine.LOCALES are rejected at the API layer.
    """
    _, actor, _ = await _create_school_and_users(db_session)
    app.dependency_overrides[require_tenant_context] = lambda: _tenant_for(actor)

    response = await api_client.patch(
        "/api/v1/settings/me",
        json={"language_preference": "fr"},
    )

    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "VALIDATION_ERROR"
    assert detail["error"]["field"] == "language_preference"

    await db_session.refresh(actor)
    assert actor.language_preference == "en"


@pytest.mark.asyncio
async def test_language_preference_reject_other_user_without_admin(
    db_session: AsyncSession, api_client: AsyncClient
):
    """
    FR-163 / ADR-09: A non-admin cannot set another user's language_preference.
    Authorization is enforced in PATCH /users/{user_id} (API layer).
    """
    _, actor, other = await _create_school_and_users(db_session)
    # Actor is checker — not admin. Real TenantContext; auth check not mocked.
    app.dependency_overrides[require_tenant_context] = lambda: _tenant_for(actor)

    response = await api_client.patch(
        f"/api/v1/users/{other.id}",
        json={"language_preference": "hi"},
    )

    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "FORBIDDEN"

    await db_session.refresh(other)
    assert other.language_preference == "en"
