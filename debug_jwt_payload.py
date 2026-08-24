import asyncio
from shared.auth import decode_access_token

async def debug_jwt():
    # This would need an actual JWT token from the frontend
    # For now, let's create a test to understand the expected structure
    print("To debug JWT payload, we need an actual token from Clerk")
    print("The token should contain:")
    print("- sub: Clerk user ID")
    print("- email: User email")
    print("- Other claims depending on Clerk configuration")
    print("\nThe require_tenant_context function expects:")
    print("- For Clerk tokens: sub claim to match clerk_user_id in database")
    print("- Fallback: email claim to match email in database")

if __name__ == "__main__":
    asyncio.run(debug_jwt())