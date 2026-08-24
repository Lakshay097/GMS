"""
Test signup/sign-in flow with existing user
"""
import sys
import asyncio
from pathlib import Path
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.database import AsyncSessionLocal
from sqlalchemy import select
from shared.models import User
from shared.auth import decode_access_token, create_access_token
from datetime import datetime, timedelta, timezone

async def test_existing_user_auth():
    """Test authentication with the existing user"""
    print("=" * 60)
    print("Testing Authentication with Existing User")
    print("=" * 60)
    
    # Get the existing user
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        if len(users) == 0:
            print("[ERROR] No users found in database")
            return
        
        user = users[0]
        print(f"\nFound existing user:")
        print(f"  Email: {user.email}")
        print(f"  User ID: {user.id}")
        print(f"  Clerk ID: {user.clerk_user_id}")
        print(f"  Roles: {user.roles}")
        print(f"  Status: {user.status}")
    
    # Test 1: Create a token with the existing user's actual Neon Auth ID
    print("\n" + "=" * 60)
    print("Test 1: Token with existing user's Neon Auth ID")
    print("=" * 60)
    
    payload_existing = {
        "sub": user.clerk_user_id,  # Use the actual Clerk ID from DB
        "email": user.email,
        "roles": user.roles,
        "school_id": str(user.school_id) if user.school_id else None,
        "department_id": str(user.department_id) if user.department_id else None,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    
    try:
        token_existing = create_access_token(payload_existing)
        print(f"[OK] Token created with existing user's Neon Auth ID")
        print(f"Token: {token_existing[:50]}...")
        
        # Test validation
        decoded = decode_access_token(token_existing)
        if decoded:
            print(f"[OK] Token validated successfully")
            print(f"Decoded payload: {decoded}")
        else:
            print(f"[ERROR] Token validation failed")
    except Exception as e:
        print(f"[ERROR] Failed to create/validate token: {e}")
    
    # Test 2: Create a token with the user's platform ID (as sub)
    print("\n" + "=" * 60)
    print("Test 2: Token with user's platform ID (as sub)")
    print("=" * 60)
    
    payload_platform = {
        "sub": str(user.id),  # Use platform ID as sub
        "email": user.email,
        "roles": user.roles,
        "school_id": str(user.school_id) if user.school_id else None,
        "department_id": str(user.department_id) if user.department_id else None,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    
    try:
        token_platform = create_access_token(payload_platform)
        print(f"[OK] Token created with platform ID")
        print(f"Token: {token_platform[:50]}...")
        
        # Test validation
        decoded = decode_access_token(token_platform)
        if decoded:
            print(f"[OK] Token validated successfully")
            print(f"Decoded payload: {decoded}")
        else:
            print(f"[ERROR] Token validation failed")
    except Exception as e:
        print(f"[ERROR] Failed to create/validate token: {e}")
    
    # Test 3: Simulate what Neon Auth would send
    print("\n" + "=" * 60)
    print("Test 3: Simulated Neon Auth token")
    print("=" * 60)
    
    # Clerk typically sends: sub (Clerk user ID), email, and maybe other claims
    payload_neon = {
        "sub": user.clerk_user_id,  # This is what Clerk would send
        "email": user.email,
        # Neon Auth might not send roles, school_id, etc.
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    
    try:
        token_neon = create_access_token(payload_neon)
        print(f"[OK] Simulated Neon Auth token created")
        print(f"Token: {token_neon[:50]}...")
        
        # Test validation
        decoded = decode_access_token(token_neon)
        if decoded:
            print(f"[OK] Token validated successfully")
            print(f"Decoded payload: {decoded}")
            
            # Now test if the middleware would resolve this to the correct user
            print("\nTesting middleware resolution...")
            async with AsyncSessionLocal() as db:
                from shared.middleware.tenancy import require_tenant_context
                from fastapi import Request
                
                # Create a mock request
                class MockRequest:
                    def __init__(self):
                        self.headers = {"Authorization": f"Bearer {token_neon}"}
                
                try:
                    # This would normally be called by FastAPI dependency injection
                    # We'll just test the user lookup logic manually
                    neon_user_id = decoded.get("sub")
                    email = decoded.get("email")
                    
                    print(f"Looking for user with clerk_user_id: {neon_user_id}")
                    result = await db.execute(
                        select(User).where(User.clerk_user_id == neon_user_id)
                    )
                    found_user = result.scalar_one_or_none()
                    
                    if found_user:
                        print(f"[OK] User found via clerk_user_id: {found_user.email}")
                    else:
                        print(f"[ERROR] User not found via clerk_user_id")
                        
                        # Try email fallback
                        if email:
                            print(f"Trying email lookup: {email}")
                            result = await db.execute(select(User).where(User.email == email))
                            found_user = result.scalar_one_or_none()
                            
                            if found_user:
                                print(f"[OK] User found via email: {found_user.email}")
                            else:
                                print(f"[ERROR] User not found via email either")
                
                except Exception as e:
                    print(f"[ERROR] Middleware test failed: {e}")
        
        else:
            print(f"[ERROR] Token validation failed")
    except Exception as e:
        print(f"[ERROR] Failed to create/validate token: {e}")
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("The authentication system should work if:")
    print("1. Clerk sends the correct clerk_user_id in the token")
    print("2. The user's clerk_user_id in the database matches")
    print("3. The token is properly signed with the correct secret")

if __name__ == "__main__":
    asyncio.run(test_existing_user_auth())