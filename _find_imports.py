"""Find files importing core models from shared.platform_models."""
import ast, os

core_names = {'User','UserRole','UserStatus','School','SchoolStatus','Department',
              'DepartmentStatus','AuditLogEntry','Permission','UserSchoolGrant'}

for root, dirs, files in os.walk('.'):
    # skip hidden dirs
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
    for f in files:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(root, f)
        try:
            src = open(fp, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        if 'from shared.platform_models import' not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == 'shared.platform_models':
                names = [n.name for n in node.names]
                if any(n in core_names for n in names):
                    print(f"{fp} -> {names}")
