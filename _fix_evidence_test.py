"""Fix test_evidence_retention.py: add neon_auth_user_id, fix status enums."""
import re

path = 'tests/acceptance/test_evidence_retention.py'
with open(path) as f:
    src = f.read()

# Add SchoolStatus, DepartmentStatus, UserStatus to imports
src = src.replace(
    'from shared.models import User, UserRole, School, Department, AuditLogEntry',
    'from shared.models import User, UserRole, UserStatus, School, SchoolStatus, Department, DepartmentStatus, AuditLogEntry'
)

# Fix School status
src = src.replace(
    'School(id=uuid4(), name="Test School", code="TS001", status="active")',
    'School(id=uuid4(), name="Test School", code="TS001", status=SchoolStatus.ACTIVE)'
)

# Fix Department status
src = src.replace(
    'Department(id=uuid4(), school_id=school.id, name="Test Dept", code="TD001", status="active")',
    'Department(id=uuid4(), school_id=school.id, name="Test Dept", code="TD001", status=DepartmentStatus.ACTIVE)'
)

# Fix User constructors — add neon_auth_user_id and fix status
# Pattern: User(\n        id=uuid4(),\n        email=...
# We need to add neon_auth_user_id after id= line

# SuperAdmin user
src = src.replace(
    '    super_admin = User(\n        id=uuid4(),\n        email="superadmin@test.com",\n        full_name="Test SuperAdmin",\n        roles=[UserRole.SUPERADMIN.value],\n        status="active"\n    )',
    '    super_admin = User(\n        id=uuid4(),\n        neon_auth_user_id=f"neon-{uuid4()}",\n        email="superadmin@test.com",\n        full_name="Test SuperAdmin",\n        roles=[UserRole.SUPERADMIN.value],\n        status=UserStatus.ACTIVE,\n    )'
)

# For the second and third tests, same pattern but school_id may differ
# Use a more general approach for remaining User blocks without neon_auth_user_id
lines = src.splitlines()
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    # Detect User( constructor start (indented)
    if re.match(r'\s+\w[\w_]* = User\($', line.rstrip()):
        # Check if neon_auth_user_id is in next 12 lines
        window = '\n'.join(lines[i+1:i+12])
        if 'neon_auth_user_id' not in window:
            indent = '    ' * (len(line) - len(line.lstrip()) // 4 + 1)
            new_lines.append('        neon_auth_user_id=f"neon-{uuid4()}",')
    i += 1
src = '\n'.join(new_lines)

# Fix remaining status="active" for User (all occurrences without the enum)
src = re.sub(r'status="active"\n    \)', 'status=UserStatus.ACTIVE,\n    )', src)

with open(path, 'w') as f:
    f.write(src)
print("Done")
