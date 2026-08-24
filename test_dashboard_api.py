"""
Test dashboard API endpoint with authentication
"""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.database import AsyncSessionLocal
from shared.middleware.tenancy import require_tenant_context
from shared.middleware.permissions import PermissionChecker
from shared.permissions import Module, Action
from shared.models import User
from sqlalchemy import select
from fastapi import Request
from unittest.mock import Mock

async def test_dashboard_auth():
    """Test dashboard with full authentication flow"""
    async with AsyncSessionLocal() as db:
        # Get a test user
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        
        if not user:
            print("No users found in database")
            return
        
        print(f"Testing with user: {user.email}, roles: {user.roles}")
        
        # Create a mock request with a fake token
        request = Mock(spec=Request)
        request.cookies = {}
        request.headers = {"Authorization": "Bearer fake_token"}
        
        try:
            # Test tenant context extraction (this will likely fail with fake token)
            from shared.auth import decode_access_token
            payload = decode_access_token("fake_token")
            print(f"Token payload: {payload}")
        except Exception as e:
            print(f"Token decode error: {e}")
        
        # Let's try creating a tenant context manually and test permission check
        from shared.middleware.tenancy import TenantContext
        tenant = TenantContext(
            user_id=str(user.id),
            school_id=str(user.school_id) if user.school_id else None,
            department_id=str(user.department_id) if user.department_id else None,
            roles=[r.value if hasattr(r, 'value') else r for r in (user.roles or [])],
            accessible_school_ids=[]
        )
        
        print(f"Tenant context: user_id={tenant.user_id}, roles={tenant.roles}")
        
        # Test permission check
        try:
            has_permission = await PermissionChecker.require_permission(
                Module.DASHBOARD, Action.VIEW, tenant, db
            )
            print(f"Permission check result: {has_permission}")
        except Exception as e:
            print(f"Permission check error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dashboard_auth())