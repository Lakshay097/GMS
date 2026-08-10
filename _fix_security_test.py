"""One-shot script: fix UserService(db) -> UserService(db, AuditLogService(db)) in test_security.py"""
import re

path = "tests/unit/test_security.py"
with open(path) as f:
    content = f.read()

old = (
    "from modules.school_dept_user_role.services.user_service import UserService\n"
    "    user_service = UserService(db)"
)
new = (
    "from modules.school_dept_user_role.services.user_service import UserService\n"
    "    from platform_services.audit_log_service.service import AuditLogService as _ALS\n"
    "    user_service = UserService(db, _ALS(db))"
)

count = content.count(old)
fixed = content.replace(old, new)

with open(path, "w") as f:
    f.write(fixed)

print(f"Replaced {count} occurrences")
