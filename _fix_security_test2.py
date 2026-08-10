"""Fix status='active' -> status=UserStatus.ACTIVE and similar in test_security.py"""
path = "tests/unit/test_security.py"
with open(path) as f:
    content = f.read()

# The test creates User(..., status="active", ...) — needs the enum object
fixed = content.replace(
    '        status="active",\n        roles=',
    '        status=UserStatus.ACTIVE,\n        roles='
)

# Also ensure UserStatus is imported in the test
if 'from shared.models import User, UserRole' in fixed and 'UserStatus' not in fixed:
    fixed = fixed.replace(
        'from shared.models import User, UserRole',
        'from shared.models import User, UserRole, UserStatus'
    )

with open(path, "w") as f:
    f.write(fixed)

changed = content.count('status="active"')
print(f"Fixed {changed} occurrences")
