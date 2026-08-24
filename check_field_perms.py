import asyncio
from sqlalchemy import text
from shared.database import get_db

async def check_perms():
    db = await anext(get_db())
    
    # Check field permissions
    result = await db.execute(text("SELECT module, field_name, role, is_allowed FROM field_permissions WHERE module = 'kpi_library' ORDER BY role, field_name"))
    print("Field Permissions:")
    print("Role | Field Name | Is Allowed")
    print("-" * 40)
    for row in result:
        print(f"{row.role} | {row.field_name} | {row.is_allowed}")
    
    # Check all user roles in the users table
    print("\n\nAll User Roles in Database:")
    print("-" * 40)
    result = await db.execute(text("SELECT id, email, roles FROM users"))
    for row in result:
        print(f"User: {row.email} | Roles: {row.roles}")

asyncio.run(check_perms())