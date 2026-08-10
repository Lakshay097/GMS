"""
Replace JSONB .contains([role]) queries with cross-DB compatible LIKE clauses.
PostgreSQL uses @> for JSONB containment; SQLite (test env) uses LIKE.
We use cast(User.roles, String).like('%"<value>"%') which works in both.
"""
import pathlib, re

TARGETS = {
    'modules/school-dept-user-role/services/school_service.py': [
        (
            'User.roles.contains([UserRole.SUPERADMIN.value]),',
            'func.cast(User.roles, String).like(\'%"superadmin"%\'),'
        ),
    ],
    'modules/school-dept-user-role/services/user_service.py': [
        (
            'User.roles.contains([UserRole.ADMIN.value]),',
            'func.cast(User.roles, String).like(\'%"admin"%\'),'
        ),
        (
            'query = query.where(User.roles.contains([role.value]))',
            'query = query.where(func.cast(User.roles, String).like(f\'%"{role.value}"%\'))'
        ),
        (
            'count_query = count_query.where(User.roles.contains([role.value]))',
            'count_query = count_query.where(func.cast(User.roles, String).like(f\'%"{role.value}"%\'))'
        ),
    ],
    'modules/kra-kpi-library/services/kpi_service.py': [
        (
            'User.roles.contains([UserRole.SUPERADMIN]),',
            'func.cast(User.roles, String).like(\'%"superadmin"%\'),'
        ),
    ],
}

# Additional import lines we need to add to each file
IMPORT_NEEDED = 'from sqlalchemy import func, String'

for fp, replacements in TARGETS.items():
    p = pathlib.Path(fp)
    src = p.read_text()
    changed = src

    for old, new in replacements:
        if old in changed:
            changed = changed.replace(old, new)
            print(f"  {fp}: replaced '{old[:50]}...'")
        else:
            print(f"  WARN {fp}: pattern not found: '{old[:60]}'")

    # Ensure the import is present
    if IMPORT_NEEDED not in changed:
        # Add after the last sqlalchemy import
        changed = re.sub(
            r'(from sqlalchemy import [^\n]+)',
            lambda m: m.group(0) + '\nfrom sqlalchemy import func, String',
            changed,
            count=1
        )
        print(f"  {fp}: added {IMPORT_NEEDED}")

    p.write_text(changed)

print("Done.")
