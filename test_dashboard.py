"""
Test script to debug dashboard endpoint
"""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.database import AsyncSessionLocal
from shared.middleware.tenancy import TenantContext
from modules.dashboards_reports_search.services.dashboard_service import DashboardService
from shared.models import User
from sqlalchemy import select

async def test_dashboard():
    """Test dashboard service directly"""
    async with AsyncSessionLocal() as db:
        # Get a test user
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        
        if not user:
            print("No users found in database")
            return
        
        print(f"Testing with user: {user.email}, roles: {user.roles}")
        
        # Create tenant context
        tenant = TenantContext(
            user_id=str(user.id),
            school_id=str(user.school_id) if user.school_id else None,
            department_id=str(user.department_id) if user.department_id else None,
            roles=[r.value if hasattr(r, 'value') else r for r in (user.roles or [])],
            accessible_school_ids=[]
        )
        
        # Test dashboard service
        service = DashboardService(db)
        try:
            dashboard = await service.get_dashboard(tenant)
            print("Dashboard data retrieved successfully:")
            print(f"Role: {dashboard.role}")
            print(f"School ID: {dashboard.school_id}")
            print(f"KPI Summary: {dashboard.kpi_summary}")
        except Exception as e:
            print(f"Error retrieving dashboard: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dashboard())