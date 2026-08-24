"""
Test the dashboard endpoint directly with proper authentication
"""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.auth import create_access_token
from shared.database import AsyncSessionLocal
from shared.models import User
from sqlalchemy import select

async def test_dashboard_endpoint():
    """Test dashboard endpoint with a real token"""
    async with AsyncSessionLocal() as db:
        # Get a test user
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        
        if not user:
            print("No users found in database")
            return
        
        print(f"Testing with user: {user.email}, roles: {user.roles}")
        
        # Create a token for this user
        token_data = {
            "sub": str(user.id),
            "id": str(user.id),
            "email": user.email,
            "roles": [r.value if hasattr(r, 'value') else r for r in (user.roles or [])],
            "school_id": str(user.school_id) if user.school_id else None,
            "department_id": str(user.department_id) if user.department_id else None
        }
        
        token = create_access_token(token_data)
        print(f"Created token: {token[:50]}...")
        
        # Test the endpoint using httpx
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/api/v1/dashboard",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text[:500]}...")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Dashboard data: role={data.get('role')}, school_id={data.get('school_id')}")
            else:
                print(f"Error response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_dashboard_endpoint())